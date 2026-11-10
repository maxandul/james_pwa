from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select, func

from james.coop_cart_agent import CoopCartDriver
from james.coop_pilot import PRODUCTS, prepare_pilot, queue_plan
from james.extensions import db
from james.models import HouseholdItem, PurchasePlan, ShopBrowser, ShopOffer, utcnow
from james.planning import coop_preview
from james.services import Conflict
from james.shop_browser_worker import schedule_coop_plan, run_pending_cart, finish
from test_app import seed_item, csrf
from test_shop_browser_pwa import enabled, record


def prepared(app, **profile_fields):
    seed_item(app)
    pid = record(app, shop_key='coop', state='idle', session_id=None, context_id='saved-coop', **profile_fields)
    with app.app_context():
        plan, created = prepare_pilot(str(uuid4()), queue=True)
        db.session.commit()
        assert created
        return pid, plan.id, plan.request_id


def test_operator_test_uses_existing_models_and_replays_never_start_again(enabled):
    pid, plan_id, request_id = prepared(enabled)
    with enabled.app_context():
        plan = db.session.get(PurchasePlan, plan_id)
        preview = coop_preview(plan)
        assert preview['ready'] and {t['sku']:t['quantity'] for t in preview['targets']} == {
            '3032108':2,'6492579':1,'3020051':1}
        assert len(plan.lines) == 3 and plan.cart_state == 'queued'
        assert db.session.scalar(select(func.count(ShopOffer.id))) == 3
        schedule_coop_plan()
        browser = db.session.get(ShopBrowser, pid)
        assert browser.state == 'queued' and browser.context_id == 'saved-coop'
        assert browser.cart_plan_id == plan_id and plan.cart_state == 'running'
        plan.cart_state = 'CART_PARTIAL'
        db.session.commit()
        again, created = prepare_pilot(request_id, queue=True)
        db.session.commit()
        assert not created and again.id == plan_id and again.cart_state == 'CART_PARTIAL'
        assert db.session.scalar(select(func.count(PurchasePlan.id))) == 1


def test_queue_expiry_never_creates_a_browser(enabled):
    pid, plan_id, _ = prepared(enabled)
    with enabled.app_context():
        plan = db.session.get(PurchasePlan, plan_id)
        plan.cart_requested_at = utcnow() - timedelta(minutes=13)
        db.session.commit()
        schedule_coop_plan()
        assert db.session.get(PurchasePlan, plan_id).cart_state == 'EXPIRED'
        assert db.session.get(ShopBrowser, pid).state == 'idle'


def test_changed_plan_never_reaches_agent(enabled, monkeypatch):
    pid, plan_id, _ = prepared(enabled)
    with enabled.app_context():
        plan = db.session.get(PurchasePlan, plan_id)
        plan.lines = [{**line, 'reserved':0} for line in plan.lines]
        db.session.commit()
        schedule_coop_plan()
        assert db.session.get(PurchasePlan, plan_id).cart_state == 'PLAN_INVALID'
        assert db.session.get(ShopBrowser, pid).state == 'idle'


def test_worker_calls_only_coop_agent_and_records_durable_result(enabled, monkeypatch):
    pid, plan_id, _ = prepared(enabled)
    def run(page, key, targets, stopped, progress):
        assert len(targets) == 3 and not stopped()
        progress(3)
        assert not stopped()
        return 'CART_READY'
    coop = Mock(side_effect=run)
    galaxus = Mock()
    monkeypatch.setattr('james.coop_cart_agent.run_coop_cart', coop)
    monkeypatch.setattr('james.shop_cart_agent.run_cart', galaxus)
    with enabled.app_context():
        schedule_coop_plan()
        browser = db.session.get(ShopBrowser, pid)
        browser.state = 'active'
        db.session.commit()
        run_pending_cart(pid, Mock())
        plan = db.session.get(PurchasePlan, plan_id)
        assert plan.cart_state == 'CART_READY' and plan.cart_actions == 3
        assert db.session.get(ShopBrowser, pid).cart_state == 'CART_READY'
        run_pending_cart(pid, Mock())
    assert coop.call_count == 1
    galaxus.assert_not_called()


def test_restart_interrupts_claimed_coop_job_without_replay(enabled):
    pid, plan_id, _ = prepared(enabled)
    provider = Mock()
    with enabled.app_context():
        schedule_coop_plan()
        finish(provider, pid, pause=lambda _:None)
        assert db.session.get(PurchasePlan, plan_id).cart_state == 'INTERRUPTED'
        schedule_coop_plan()
        assert db.session.get(ShopBrowser, pid).state == 'idle'
    provider.create_session.assert_not_called()


def test_coop_preview_post_requires_consent_version_and_csrf(enabled, client):
    pid, plan_id, _ = prepared(enabled, confirmed_at=utcnow())
    path = f'/shop-browser/coop/preview/{plan_id}'
    with enabled.app_context():
        plan = db.session.get(PurchasePlan, plan_id)
        plan.cart_state = None
        db.session.commit()
        version = plan.version
    assert client.post(path, data={'consent':'yes','version':version}).status_code == 400
    token = csrf(client, path)
    assert client.post(path, data={'csrf_token':token, 'version':version}).status_code == 400
    assert client.post(path, data={'csrf_token':token, 'version':version+1, 'consent':'yes'}).status_code == 409
    assert client.post(path, data={'csrf_token':token, 'version':version, 'consent':'yes'}).status_code == 302
    assert client.post(path, data={'csrf_token':token, 'version':version, 'consent':'yes'}).status_code == 409


def test_provider_failure_is_terminal_and_does_not_replay(enabled, monkeypatch):
    from james.shop_browser_worker import worker_once
    from scripts.shop_browser_context import BrowserUnavailable
    pid, plan_id, _ = prepared(enabled)
    provider = Mock()
    provider.create_session.side_effect = BrowserUnavailable('synthetic', status=402)
    monkeypatch.setattr('james.shop_browser_worker.Browserbase', lambda *a:provider)
    with enabled.app_context():
        worker_once(enabled)
        assert db.session.get(PurchasePlan, plan_id).cart_state == 'PROVIDER_HTTP_402'
        assert db.session.get(ShopBrowser, pid).cart_state == 'PROVIDER_HTTP_402'
        assert db.session.get(ShopBrowser, pid).context_id == 'saved-coop'
        worker_once(enabled)
    assert provider.create_session.call_count == 1


def driver():
    page = Mock()
    page.url = PRODUCTS[0]['url']
    return CoopCartDriver(page, [{'sku':p['sku'],'quantity':p['quantity']} for p in PRODUCTS], lambda:False, Mock())


def test_coop_add_is_bound_to_main_product_not_recommendations():
    d = driver()
    control = {'tag':'BUTTON','add':True,'test':'productbasket','product':'3032108'}
    assert d.permitted(control)
    assert not d.permitted({**control,'test':'productlistbasket3032108'})
    assert not d.permitted({**control,'product':'6492579'})
    assert not d.permitted({**control,'product':None})


@pytest.mark.parametrize('url', ['https://evil.test/de/cart', 'https://www.coop.ch/de/checkout',
    'https://www.coop.ch/de/cart?checkout=true','https://www.coop.ch/de/login/popup',
    'https://www.coop.ch/de/test/p/999', 'https://www.coop.ch/de/test/p/3032108?redirect=checkout'])
def test_coop_checkout_unknown_product_and_guest_login_blocked(url):
    assert not driver().safe_link(url)


def test_coop_search_result_tracking_and_exact_product_are_allowed():
    d = driver()
    assert d.safe_link(PRODUCTS[0]['url'] + '?context=search')
    assert d.safe_link('https://www.coop.ch/de/cart')
    assert d.safe_link('https://www.coop.ch/de/search/?text=3032108')
    for label in ('Zur Kasse','Jetzt bestellen','Entfernen','+','-'):
        assert not d.permitted({'tag':'BUTTON','label':label})


def test_uncertain_coop_add_consumes_click_budget():
    d = driver()
    d.page.evaluate.return_value = {'tag':'BUTTON','add':True,'test':'productbasket','product':'3032108'}
    d.page.mouse.click.side_effect = TimeoutError('synthetic')
    for _ in range(2):
        with pytest.raises(TimeoutError):
            d.click(SimpleNamespace(button='left',keys=[],x=3,y=4))
    with pytest.raises(RuntimeError):
        d.click(SimpleNamespace(button='left',keys=[],x=3,y=4))
    assert d.page.mouse.click.call_count == 2
