"""Exact Coop identity, retained Galaxus profile, and read-only preparation."""
from datetime import timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from james.assortment import bind_shop, save_offer, save_product
from james.extensions import db
from james.models import HouseholdItem, Product, PurchasePlan, PurchaseSource, ShopBrowser, ShopOffer, ShoppingNeed, utcnow
from james.planning import coop_preview
from james.services import Conflict
from james.shops import coop_product_id, offer_problems
from test_app import csrf, login, seed_item, action
from test_assortment import offer, source, variant
from test_plans import make_plan
from test_shop_browser_pwa import enabled, record

URL = 'https://www.coop.ch/de/lebensmittel/test-milch/p/4407235'


def post_shop(client, action='open', version=0, shop='coop'):
    path = f'/shop-browser/{shop}'
    return client.post(path, data={'csrf_token': csrf(client, path),
        'version': str(version), 'action': action, 'consent': 'yes'})


def exact_offer(app, *, confirm=True, units='1'):
    item_id, home, user = seed_item(app)
    product_id = variant(app, home, item_id, 'Naturaplan Vollmilch UHT')
    source_id = source(app, home, 'Coop')
    offer_id = offer(app, home, item_id, product_id, source_id,
        units_per_pack=units, url=URL, shop_sku='4407235',
        confirm_exact='1' if confirm else '')
    return item_id, home, user, product_id, source_id, offer_id


def test_coop_and_galaxus_profiles_are_separate_and_serialized(enabled, client):
    galaxus_id = record(enabled, state='idle', session_id=None, context_id='saved-galaxus')
    assert post_shop(client).status_code == 302
    assert post_shop(client, shop='galaxus', version=1).status_code == 409
    with enabled.app_context():
        profiles = db.session.scalars(select(ShopBrowser).order_by(ShopBrowser.id)).all()
        assert len(profiles) == 2 and profiles[1].shop_key == 'coop'
        assert profiles[1].context_id is None
        assert db.session.get(ShopBrowser, galaxus_id).context_id == 'saved-galaxus'
        assert profiles[0].state == 'idle'
    html = client.get('/shop-browser/coop').text
    assert 'Coop verbinden' in html and '{{ shop.name }}' not in html
    assert 'Warenkorbtest starten' not in html


def test_coop_cart_cannot_use_fixed_galaxus_agent(enabled, client, monkeypatch):
    from james.shop_browser_worker import run_pending_cart
    pid = record(enabled, shop_key='coop', confirmed_at=utcnow(), cart_state='queued')
    assert post_shop(client, 'cart', version=1).status_code == 400
    agent = Mock()
    monkeypatch.setattr('james.shop_cart_agent.run_cart', agent)
    with enabled.app_context():
        run_pending_cart(pid, Mock())
        assert db.session.get(ShopBrowser, pid).cart_state == 'UNSUPPORTED_SHOP'
    agent.assert_not_called()


def test_coop_reuses_its_own_context_and_opens_coop(enabled, monkeypatch):
    import sys
    from types import SimpleNamespace
    from contextlib import nullcontext
    from james.shop_browser_worker import connect
    pid = record(enabled, shop_key='coop', state='creating', session_id=None,
        context_id='11111111-1111-4111-8111-111111111111')
    provider = Mock()
    provider.live_url.return_value = 'https://www.browserbase.com/synthetic-test'
    provider.create_session.return_value = {'id':'22222222-2222-4222-8222-222222222222', 'connectUrl':'wss://synthetic.test'}
    page = Mock()
    def tick(_):
        db.session.get(ShopBrowser, pid).state = 'closing'
        db.session.commit()
    page.wait_for_timeout.side_effect = tick
    browser = SimpleNamespace(contexts=[SimpleNamespace(pages=[page])])
    pw = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=Mock(return_value=browser)))
    monkeypatch.setitem(sys.modules, 'playwright.sync_api', SimpleNamespace(sync_playwright=lambda:nullcontext(pw)))
    monkeypatch.setattr('james.shop_browser_worker.finish', Mock())
    with enabled.app_context():
        connect(provider, pid)
    provider.create_context.assert_not_called()
    provider.create_session.assert_called_once_with('11111111-1111-4111-8111-111111111111', keep_alive=False)
    page.goto.assert_called_once_with('https://www.coop.ch/de/', wait_until='domcontentloaded', timeout=30000)


@pytest.mark.parametrize('url', [
    'https://www.coop.ch.evil.test/de/test/p/4407235',
    'https://evil.test/de/test/p/4407235',
    'http://www.coop.ch/de/test/p/4407235',
    'https://www.coop.ch/de/test/p/4407235?redirect=evil',
    'https://www.coop.ch/de/test/p/4407235#other',
    'https://user@www.coop.ch/de/test/p/4407235',
    'https://www.coop.ch/de/test/p/not-an-id',
])
def test_coop_ids_require_exact_product_url(url):
    assert coop_product_id(url) is None


def test_confirmed_offer_and_full_snapshot_round_packs_visibly(enabled, client):
    item_id, home, _, product_id, shop, oid = exact_offer(enabled, units='3')
    action(client, item_id, 'replenish', 1)
    path, _ = make_plan(client, item_id, shop, 2)
    with enabled.app_context():
        plan = db.session.scalar(select(PurchasePlan))
        data = coop_preview(plan)
        assert data['ready'] and not data['problems']
        assert data['targets'][0]['quantity'] == 1
        assert data['targets'][0]['extra'] == 1
        assert plan.lines[0]['shop_identity']['shop_sku'] == '4407235'
        assert plan.lines[0]['shop_identity']['package_text'] == '1 Liter'
        assert db.session.get(HouseholdItem, item_id).stock_status == 'low'
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2
        plan_id = plan.id
    response = client.get(f'/shop-browser/coop/preview/{plan_id}')
    assert response.status_code == 200
    assert '4407235' in response.text and 'Mehrmenge durch Packungsrundung: 1' in response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'Coop-Testvorschau' in client.get(path).text


@pytest.mark.parametrize('change', ['package', 'sku', 'units', 'source', 'inactive', 'preference'])
def test_changes_block_old_confirmations_or_old_plan(enabled, client, change):
    item_id, home, _, product_id, shop, oid = exact_offer(enabled)
    action(client, item_id, 'replenish', 1)
    make_plan(client, item_id, shop, 2)
    with enabled.app_context():
        saved = db.session.get(ShopOffer, oid)
        if change == 'package':
            product = db.session.get(Product, product_id)
            save_product(home, item_id, {'product_name': product.name, 'package_text':'6 × 1 Liter',
                'version':str(product.version)}, product_id)
        elif change == 'source':
            bind_shop(db.session.get(PurchaseSource, shop), '')
        elif change == 'inactive':
            saved.active = False
        elif change == 'preference':
            saved.preferred = not saved.preferred
        else:
            save_offer(home, item_id, product_id, {'version':str(saved.version), 'source_id':str(shop),
                'url':URL, 'shop_sku':'999' if change == 'sku' else '4407235',
                'units_per_pack':'6' if change == 'units' else '1'}, oid)
        db.session.commit()
        data = coop_preview(db.session.scalar(select(PurchasePlan)))
        assert not data['ready'] and data['problems']


def test_incomplete_and_mismatched_mapping_cannot_be_confirmed(app):
    item_id, home, _, product_id, shop, oid = exact_offer(app, confirm=False)
    with app.app_context():
        saved = db.session.get(ShopOffer, oid)
        assert offer_problems(saved)
        with pytest.raises(ValueError, match='übereinstimmen'):
            save_offer(home, item_id, product_id, {'source_id':str(shop), 'version':str(saved.version),
                'units_per_pack':'1', 'url':URL, 'shop_sku':'999', 'confirm_exact':'1'}, oid)
        db.session.rollback()
        assert db.session.get(ShopOffer, oid).shop_sku == '4407235'


def test_duplicate_sku_cannot_be_confirmed(app):
    item_id, home, _, product_id, shop, oid = exact_offer(app)
    second = variant(app, home, item_id, 'Andere Packung')
    with app.app_context():
        with pytest.raises(Conflict, match='bereits'):
            save_offer(home, item_id, second, {'source_id':str(shop), 'units_per_pack':'1',
                'url':URL, 'shop_sku':'4407235', 'confirm_exact':'1'})
        db.session.rollback()


def test_source_merge_cannot_transfer_coop_product_ids(app, client):
    item_id, home, _, product_id, shop, oid = exact_offer(app)
    login(client)
    migros = source(app, home, 'Migros')
    response = client.post('/settings/catalogue/source', data={
        'csrf_token':csrf(client, '/settings/catalogue/source'), 'action':'retire',
        'entry_id':str(shop), 'version':'1', 'replacement_id':str(migros)})
    assert response.status_code == 409
    with app.app_context():
        saved = db.session.get(ShopOffer, oid)
        assert saved.source_id == shop and not offer_problems(saved)


def test_old_plan_without_exact_snapshot_is_blocked(enabled, client):
    item_id, home, _, product_id, shop, oid = exact_offer(enabled)
    action(client, item_id, 'replenish', 1)
    make_plan(client, item_id, shop, 2)
    with enabled.app_context():
        plan = db.session.scalar(select(PurchasePlan))
        plan.lines = [{k:v for k,v in line.items() if k != 'shop_identity'} for line in plan.lines]
        db.session.commit()
        assert not coop_preview(plan)['ready']


@pytest.mark.parametrize('email', ['member@example.test', 'other@example.test'])
def test_private_coop_routes_reject_other_people(enabled, client, email):
    item_id, home, _, product_id, shop, oid = exact_offer(enabled)
    action(client, item_id, 'replenish', 1)
    path, _ = make_plan(client, item_id, shop, 2)
    plan_id = path.rsplit('/', 1)[1]
    client.post('/logout', data={'csrf_token':csrf(client, '/')})
    login(client, email)
    assert client.get('/shop-browser/coop').status_code == 403
    assert client.get('/shop-browser/coop/live').status_code == 403
    assert client.get(f'/shop-browser/coop/preview/{plan_id}').status_code == 403
