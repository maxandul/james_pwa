from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from james.extensions import db
from james.models import Membership, ShopLogin, User, utcnow
from james.shop_login import ProviderUnavailable
from james.shop_login_worker import cleanup, worker_once
from test_app import csrf, login


@pytest.fixture
def prepared(app, client, monkeypatch):
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key')
    login(client)
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == 'owner@example.test'))
        member = db.session.scalar(select(Membership).where(Membership.user_id == user.id))
        run = ShopLogin(user_id=user.id, household_id=member.household_id, auth_version=user.auth_version,
            session_id='synthetic-session', request_id='request-1', turn_id='turn-1', state='pending',
            expires_at=utcnow() + timedelta(minutes=6), challenge_expires_at=utcnow() + timedelta(minutes=2))
        db.session.add(run)
        db.session.commit()
        identifier = run.id
    calls = []
    schema = {'type': 'browser_authentication', 'credential_origin': 'https://www.galaxus.ch',
        'fields': [{'id': 'email', 'label': '<script>email</script>', 'type': 'email', 'required': True},
                   {'id': 'password', 'label': 'Passwort', 'type': 'password', 'required': True}], 'options': []}
    def provider(method, path, body=None):
        calls.append((method, path, body))
        if method == 'GET':
            return {'status': 'requires_action', 'required_actions': [{
                'type': 'computer_use_approval_request', 'request_id': 'request-1', 'turn_id': 'turn-1', 'request': schema}]}
        return {}
    monkeypatch.setattr('james.shop_login.api', provider)
    return identifier, calls, schema


def form(client, identifier, **changes):
    data = {'csrf_token': csrf(client, f'/shop-login/{identifier}'), 'request_id': 'request-1',
        'destination_confirmed': 'yes', 'action': 'submit', 'option': '',
        'value_0': 'synthetic@example.test', 'value_1': 'synthetic-private-password'}
    data.update(changes)
    return data


def test_disabled_pilot_has_no_link_or_provider_call(app, client, monkeypatch):
    login(client)
    monkeypatch.setattr('james.shop_login.api', lambda *a: pytest.fail('must not call API'))
    assert client.get('/shop-login').status_code == 404
    assert b'/shop-login' not in client.get('/').data


def test_private_form_escapes_schema_and_never_exposes_session_identifier(client, prepared):
    identifier, _, _ = prepared
    response = client.get(f'/shop-login/{identifier}')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert b'&lt;script&gt;email&lt;/script&gt;' in response.data
    assert b'synthetic-session' not in response.data


def test_credentials_relay_once_without_database_or_response_persistence(app, client, prepared):
    identifier, calls, _ = prepared
    data = form(client, identifier)
    assert client.post(f'/shop-login/{identifier}', data=data).status_code == 302
    assert client.post(f'/shop-login/{identifier}', data=data).status_code == 200
    posts = [c for c in calls if c[0] == 'POST']
    assert len(posts) == 1
    response = client.get(f'/shop-login/{identifier}')
    assert b'synthetic-private-password' not in response.data
    assert b'synthetic@example.test' not in response.data
    with app.app_context():
        run = db.session.get(ShopLogin, identifier)
        assert run.state == 'accepted'
        assert 'synthetic-private-password' not in repr({c.name: getattr(run, c.name) for c in run.__table__.columns})


@pytest.mark.parametrize('changes,status', [
    ({'csrf_token': 'bad'}, 400), ({'request_id': 'old'}, 409),
    ({'destination_confirmed': ''}, 409), ({'value_1': ''}, 400),
    ({'value_2': 'extra'}, 400), ({'option': 'unknown'}, 400), ({'action': 'bad'}, 400),
])
def test_invalid_posts_never_forward_credentials(client, prepared, changes, status):
    identifier, calls, _ = prepared
    data = form(client, identifier, **changes)
    assert client.post(f'/shop-login/{identifier}', data=data).status_code == status
    assert not [c for c in calls if c[0] == 'POST']


def test_other_household_and_same_household_member_cannot_access(client, prepared):
    identifier, calls, _ = prepared
    for email in ('member@example.test', 'other@example.test'):
        client.post('/logout', data={'csrf_token': csrf(client, '/')})
        login(client, email)
        assert client.get(f'/shop-login/{identifier}').status_code == 404
        assert f'/shop-login/{identifier}'.encode() not in client.get('/shop-login').data
    assert not calls


def test_revocation_and_expiry_prevent_provider_submission(app, client, prepared):
    identifier, calls, _ = prepared
    data = form(client, identifier)
    with app.app_context():
        db.session.get(ShopLogin, identifier).challenge_expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()
    assert client.post(f'/shop-login/{identifier}', data=data).status_code == 410
    assert not [c for c in calls if c[0] == 'POST']
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == 'owner@example.test'))
        user.auth_version += 1
        db.session.commit()
    assert client.get(f'/shop-login/{identifier}').status_code == 302


def test_wrong_origin_never_renders_credential_fields(client, prepared):
    identifier, calls, schema = prepared
    schema['credential_origin'] = 'https://www.galaxus.ch.evil.example'
    assert client.get(f'/shop-login/{identifier}').status_code == 410
    assert not [c for c in calls if c[0] == 'POST']


def test_uncertain_result_is_not_replayed(app, client, prepared, monkeypatch):
    identifier, calls, _ = prepared
    data = form(client, identifier)
    from james import shop_login as module
    original = module.api
    def failure(method, path, body=None):
        if method == 'POST':
            calls.append((method, path, body))
            raise ProviderUnavailable('synthetic-private-password')
        return original(method, path, body)
    monkeypatch.setattr(module, 'api', failure)
    assert client.post(f'/shop-login/{identifier}', data=data).status_code == 302
    assert client.post(f'/shop-login/{identifier}', data=data).status_code == 200
    assert len([c for c in calls if c[0] == 'POST']) == 1
    assert b'synthetic-private-password' not in client.get(f'/shop-login/{identifier}').data
    with app.app_context():
        assert db.session.get(ShopLogin, identifier).state == 'unknown'


def test_logout_cancels_pending_pilot(app, client, prepared):
    identifier, calls, _ = prepared
    assert client.post('/logout', data={'csrf_token': csrf(client, '/')}).status_code == 302
    with app.app_context():
        assert db.session.get(ShopLogin, identifier).state == 'cancelled'
    assert not calls


def test_cleanup_cannot_delete_unrelated_api_session(app, prepared, monkeypatch):
    identifier, _, _ = prepared
    calls = []
    def provider(method, path, body=None):
        calls.append(method)
        return {'metadata': {'james_login_run': str(uuid4())}, 'status': 'idle'}
    monkeypatch.setattr('james.shop_login_worker.api', provider)
    with app.app_context():
        assert cleanup(identifier) is False
        assert db.session.get(ShopLogin, identifier).state == 'cleanup_pending'
    assert calls == ['GET']


def test_cleanup_confirms_remote_deletion_before_closing(app, prepared, monkeypatch):
    identifier, _, _ = prepared
    with app.app_context():
        reference = db.session.get(ShopLogin, identifier).reference
    calls = []
    def provider(method, path, body=None):
        calls.append(method)
        return {'metadata': {'james_login_run': reference}, 'status': 'requires_action'} if method == 'GET' else {}
    monkeypatch.setattr('james.shop_login_worker.api', provider)
    with app.app_context():
        assert cleanup(identifier) is True
        assert db.session.get(ShopLogin, identifier).state == 'closed'
    assert calls == ['GET', 'POST', 'DELETE']


def test_start_requires_explicit_consent_and_is_idempotent(app, client, monkeypatch):
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key')
    login(client)
    monkeypatch.setattr('james.shop_login.api', lambda *a: pytest.fail('Start must only queue, not call API'))
    data = {'csrf_token': csrf(client, '/shop-login'), 'start_request_id': str(uuid4())}
    assert client.post('/shop-login', data=data).status_code == 400
    data['cost_consent'] = 'yes'
    first = client.post('/shop-login', data=data)
    assert first.status_code == 302
    assert client.post('/shop-login', data=data).location == first.location
    assert client.post('/shop-login', data={**data, 'start_request_id': str(uuid4())}).status_code == 409
    with app.app_context():
        runs = db.session.scalars(select(ShopLogin)).all()
        assert len(runs) == 1 and runs[0].state == 'queued'
        assert runs[0].cost_authorized_at is not None


def test_cancelled_queue_never_creates_remote_session(app, client, monkeypatch):
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key')
    login(client)
    data = {'csrf_token': csrf(client, '/shop-login'), 'start_request_id': str(uuid4()), 'cost_consent': 'yes'}
    response = client.post('/shop-login', data=data)
    path = response.location
    client.post(path, data={'csrf_token': csrf(client, path), 'action': 'cancel'})
    monkeypatch.setattr('james.shop_login_worker.api', lambda *a: pytest.fail('No session existed'))
    monkeypatch.setattr('james.shop_login_worker.execute_run', lambda *a: pytest.fail('Cancelled work must not execute'))
    with app.app_context():
        assert worker_once(app) is False
        run = db.session.scalar(select(ShopLogin))
        assert run.state == 'closed' and run.active_user_id is None


def test_worker_claims_job_only_once(app, client, monkeypatch):
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key')
    login(client)
    client.post('/shop-login', data={'csrf_token': csrf(client, '/shop-login'),
        'start_request_id': str(uuid4()), 'cost_consent': 'yes'})
    executed = []
    monkeypatch.setattr('james.shop_login_worker.execute_run', lambda app, identifier: executed.append(identifier))
    with app.app_context():
        assert worker_once(app) is True
        assert worker_once(app) is False
        assert len(executed) == 1


def test_missing_cost_consent_is_rejected_by_executor_without_api(app, prepared, monkeypatch):
    identifier, _, _ = prepared
    from james.shop_login_worker import execute_run
    monkeypatch.setattr('james.shop_login_worker.api', lambda *a: pytest.fail('Must not call API'))
    with app.app_context():
        run = db.session.get(ShopLogin, identifier)
        run.session_id = None
        run.state = 'creating'
        run.cost_authorized_at = None
        db.session.commit()
        execute_run(app, identifier)
        assert db.session.get(ShopLogin, identifier).state == 'closed'


def test_status_change_during_provider_read_removes_form(app, client, prepared, monkeypatch):
    identifier, calls, _ = prepared
    from james import shop_login as module
    original = module.api
    def revoked(method, path, body=None):
        result = original(method, path, body)
        db.session.get(ShopLogin, identifier).state = 'cancelled'
        db.session.commit()
        return result
    monkeypatch.setattr(module, 'api', revoked)
    assert client.get(f'/shop-login/{identifier}').status_code == 410
    assert not [c for c in calls if c[0] == 'POST']


def test_executor_registers_session_before_task_and_clears_active_slot(app, prepared, monkeypatch):
    identifier, _, _ = prepared
    from unittest.mock import MagicMock
    from james.shop_login_worker import execute_run
    monkeypatch.setattr('openai.OpenAI', MagicMock())
    observed = []
    def fake_run(client, url, path, **options):
        options['session_handler']('synthetic-created-session')
        with app.app_context():
            row = db.session.get(ShopLogin, identifier)
            observed.append((row.state, row.session_id, row.reference))
        assert options['authentication_handler'] is not None
        assert options['session_metadata']['james_login_run'] == observed[-1][2]
        assert options['authorized_uncapped_test'] is True
        assert 'screenshot_path' not in options
        return {'status': 'turn_completed', 'cleanup': 'deleted'}
    monkeypatch.setattr('scripts.jayjay_browser_probe.run_task', fake_run)
    with app.app_context():
        run = db.session.get(ShopLogin, identifier)
        run.session_id = None
        run.state = 'creating'
        run.cost_authorized_at = utcnow()
        db.session.commit()
        execute_run(app, identifier)
        db.session.expire_all()
        assert db.session.get(ShopLogin, identifier).state == 'closed'
        assert db.session.get(ShopLogin, identifier).active_user_id is None
        execute_run(app, identifier)
    assert len(observed) == 1 and observed[0][:2] == ('running', 'synthetic-created-session')


def test_daily_start_limit_includes_completed_and_cancelled_attempts(app, client):
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key')
    login(client)
    for _ in range(2):
        response = client.post('/shop-login', data={'csrf_token': csrf(client, '/shop-login'),
            'start_request_id': str(uuid4()), 'cost_consent': 'yes'})
        assert response.status_code == 302
        with app.app_context():
            row = db.session.scalars(select(ShopLogin).order_by(ShopLogin.id.desc())).first()
            row.state, row.active_user_id = 'closed', None
            db.session.commit()
    response = client.post('/shop-login', data={'csrf_token': csrf(client, '/shop-login'),
        'start_request_id': str(uuid4()), 'cost_consent': 'yes'})
    assert response.status_code == 409
