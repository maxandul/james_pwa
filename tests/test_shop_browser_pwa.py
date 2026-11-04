from datetime import timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from james.extensions import db
from james.models import ShopBrowser, User, Membership, utcnow
from james.shop_browser_worker import worker_once, finish
from scripts.shop_browser_context import BrowserUnavailable
from test_app import login, csrf


@pytest.fixture
def enabled(app, client):
    app.config.update(SHOP_BROWSER_ENABLED=True, BROWSERBASE_API_KEY='synthetic-only',
                      BROWSERBASE_PROJECT_ID='33333333-3333-4333-8333-333333333333')
    login(client)
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == 'owner@example.test'))
        member = db.session.scalar(select(Membership).where(Membership.user_id == user.id))
        app.config['GALAXUS_HOUSEHOLD_ID'] = str(member.household_id)
    return app


def post(client, action='open', version=0, consent='yes'):
    token = csrf(client, '/shop-browser')
    return client.post('/shop-browser', data={'csrf_token': token, 'action': action,
                       'version': str(version), 'consent': consent})


def record(app, **fields):
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == 'owner@example.test'))
        member = db.session.scalar(select(Membership).where(Membership.user_id == user.id))
        item = ShopBrowser(household_id=member.household_id, user_id=user.id,
            auth_version=user.auth_version, state='active', context_id='context',
            session_id='session', live_url='https://www.browserbase.com/private-test',
            expires_at=utcnow()+timedelta(minutes=10))
        for k,v in fields.items():
            setattr(item,k,v)
        db.session.add(item)
        db.session.commit()
        return item.id


def test_feature_off(client):
    assert client.get('/shop-browser').status_code == 404


def test_open_is_queued_and_replay_cannot_create_twice(enabled, client):
    assert post(client).status_code == 302
    assert post(client).status_code == 409
    with enabled.app_context():
        items = db.session.scalars(select(ShopBrowser)).all()
        assert len(items) == 1 and items[0].state == 'queued'
        assert items[0].session_id is None
        assert 700 < (items[0].expires_at-utcnow()).total_seconds() <= 720


def test_consent_and_csrf(enabled, client):
    assert client.post('/shop-browser', data={'action':'open'}).status_code == 400
    assert post(client, consent='').status_code == 400


@pytest.mark.parametrize('email', ['member@example.test', 'other@example.test'])
def test_other_user_cannot_view_control_link(enabled, client, email):
    record(enabled)
    client.post('/logout', data={'csrf_token': csrf(client, '/shop-browser')})
    login(client, email=email)
    assert client.get('/shop-browser').status_code == 403
    assert client.get('/shop-browser/live').status_code == 403


def test_live_link_is_private_and_expires(enabled, client):
    pid = record(enabled)
    response = client.get('/shop-browser/live')
    assert response.status_code == 302
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'private-test' not in client.get('/shop-browser').text
    with enabled.app_context():
        db.session.get(ShopBrowser,pid).expires_at=utcnow()-timedelta(seconds=1)
        db.session.commit()
    assert client.get('/shop-browser/live').status_code == 410


def test_close_revokes_link_immediately(enabled, client):
    record(enabled)
    assert post(client,'close',1).status_code == 302
    assert client.get('/shop-browser/live').status_code == 410


def test_unknown_creation_is_not_reset(enabled, client):
    record(enabled, state='error', error_category='creation_unknown', session_id=None)
    assert post(client,'forget',1).status_code == 409


def test_restart_does_not_replay_creation(enabled, monkeypatch):
    pid=record(enabled,state='creating',context_id=None,session_id=None)
    provider=Mock()
    monkeypatch.setattr('james.shop_browser_worker.Browserbase',lambda *args:provider)
    with enabled.app_context():
        worker_once(enabled)
        item=db.session.get(ShopBrowser,pid)
        assert item.state=='error' and item.error_category=='creation_unknown'
        worker_once(enabled)
    provider.create_session.assert_not_called()
    provider.create_context.assert_not_called()


def test_finish_retains_context_until_explicit_forget(enabled):
    pid=record(enabled)
    provider=Mock()
    provider.session.return_value={'status':'COMPLETED'}
    with enabled.app_context():
        finish(provider,pid,pause=lambda _:None)
        item=db.session.get(ShopBrowser,pid)
        assert item.state=='idle' and item.session_id is None and item.context_id=='context'
        finish(provider,pid,forget=True,pause=lambda _:None)
        assert db.session.get(ShopBrowser,pid).context_id is None
    provider.delete_context.assert_called_once_with('context')


def test_cleanup_failure_retains_forget_intent(enabled, monkeypatch):
    pid=record(enabled,state='forgetting')
    provider=Mock()
    provider.session.side_effect=BrowserUnavailable('offline')
    monkeypatch.setattr('james.shop_browser_worker.Browserbase',lambda *args:provider)
    with enabled.app_context():
        worker_once(enabled)
        item=db.session.get(ShopBrowser,pid)
        assert item.state=='forgetting' and item.session_id=='session'
        assert item.live_url is None


def test_revoked_user_profile_is_deleted_even_when_idle(enabled, monkeypatch):
    pid=record(enabled,state='idle',session_id=None)
    provider=Mock()
    monkeypatch.setattr('james.shop_browser_worker.Browserbase',lambda *args:provider)
    with enabled.app_context():
        item=db.session.get(ShopBrowser,pid)
        db.session.get(User,item.user_id).active=False
        db.session.commit()
        worker_once(enabled)
        assert db.session.get(ShopBrowser,pid).context_id is None
    provider.delete_context.assert_called_once_with('context')


def test_connected_worker_uses_free_plan_and_holds_browser(enabled, monkeypatch):
    import sys
    from types import SimpleNamespace
    from contextlib import nullcontext
    from james.shop_browser_worker import connect
    pid = record(enabled, state='creating', session_id=None, context_id='11111111-1111-4111-8111-111111111111')
    p = Mock()
    p.create_session.return_value={'id':'22222222-2222-4222-8222-222222222222', 'connectUrl':'wss://connect.browserbase.com/test'}
    p.live_url.return_value='https://www.browserbase.com/test'
    page=Mock()
    def tick(_):
        item=db.session.get(ShopBrowser,pid)
        assert item.state=='active'
        item.state='closing'
        db.session.commit()
    page.wait_for_timeout.side_effect=tick
    browser=SimpleNamespace(contexts=[SimpleNamespace(pages=[page])])
    pw=SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=Mock(return_value=browser)))
    monkeypatch.setitem(sys.modules,'playwright.sync_api',SimpleNamespace(sync_playwright=lambda:nullcontext(pw)))
    cleanup=Mock()
    monkeypatch.setattr('james.shop_browser_worker.finish',cleanup)
    with enabled.app_context():
        connect(p,pid)
    assert p.create_session.call_args.kwargs == {'keep_alive':False}
    page.goto.assert_called_once_with('https://www.galaxus.ch/',wait_until='domcontentloaded',timeout=30000)
    cleanup.assert_called_once()


def test_cart_requires_confirmed_live_account_and_consent(enabled, client):
    pid = record(enabled)
    assert post(client, 'cart', 1).status_code == 409
    assert post(client, 'confirm', 1).status_code == 302
    assert post(client, 'cart', 2, consent='').status_code == 400
    assert post(client, 'cart', 2).status_code == 302
    assert post(client, 'cart', 2).status_code == 409
    with enabled.app_context():
        item = db.session.get(ShopBrowser, pid)
        assert item.cart_state == 'queued'
        version = item.version
    assert post(client, 'cart', version).status_code == 409


def test_cart_cannot_start_near_timeout(enabled, client):
    record(enabled, confirmed_at=utcnow(), expires_at=utcnow()+timedelta(seconds=120))
    assert post(client, 'cart', 1).status_code == 409


def test_restart_marks_cart_interrupted_never_replays(enabled, monkeypatch):
    pid = record(enabled, cart_state='running')
    provider = Mock()
    provider.session.return_value = {'status': 'COMPLETED'}
    monkeypatch.setattr('james.shop_browser_worker.Browserbase', lambda *a: provider)
    monkeypatch.setattr('james.shop_browser_worker.finish',
                        lambda p, i, **kw: finish(p, i, pause=lambda _: None, **kw))
    agent = Mock()
    monkeypatch.setattr('james.shop_cart_agent.run_cart', agent)
    with enabled.app_context():
        worker_once(enabled)
        assert db.session.get(ShopBrowser, pid).cart_state == 'INTERRUPTED'
    agent.assert_not_called()


def test_cart_worker_preserves_close_request(enabled, monkeypatch):
    from james.shop_browser_worker import run_pending_cart
    pid = record(enabled, cart_state='queued', confirmed_at=utcnow())
    def run(page, key, stopped, progress):
        assert not stopped()
        progress(2)
        item = db.session.get(ShopBrowser, pid)
        item.state = 'closing'
        db.session.commit()
        assert stopped()
        return 'INTERRUPTED'
    agent = Mock(side_effect=run)
    monkeypatch.setattr('james.shop_cart_agent.run_cart', agent)
    with enabled.app_context():
        run_pending_cart(pid, Mock())
        item = db.session.get(ShopBrowser, pid)
        assert item.state == 'closing' and item.cart_state == 'INTERRUPTED'
        assert item.cart_actions == 2
        run_pending_cart(pid, Mock())
    assert agent.call_count == 1
