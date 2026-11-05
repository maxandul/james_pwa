from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from james.extensions import db
from james.models import Membership, ShopLogin, User, utcnow
from james.shop_login import ProviderUnavailable
from james.shop_login_worker import cleanup, worker_once
from test_app import csrf, login


@pytest.fixture(autouse=True)
def bound_account(app):
    with app.app_context():
        owner = db.session.scalar(select(User).where(User.email == 'owner@example.test'))
        member = db.session.scalar(select(Membership).where(Membership.user_id == owner.id))
        app.config.update(SHOP_CART_PILOT_ENABLED=True, GALAXUS_HOUSEHOLD_ID=str(member.household_id),
            GALAXUS_EMAIL='synthetic-account@example.test', GALAXUS_PASSWORD='synthetic-account-password')


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
            row.state, row.active_user_id, row.active_household_id = 'closed', None, None
            db.session.commit()
    response = client.post('/shop-login', data={'csrf_token': csrf(client, '/shop-login'),
        'start_request_id': str(uuid4()), 'cost_consent': 'yes'})
    assert response.status_code == 409


def test_household_member_can_start_but_cannot_overlap_shared_account(app, client):
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key')
    login(client)
    payload = {'csrf_token': csrf(client, '/shop-login'), 'start_request_id': str(uuid4()), 'cost_consent': 'yes'}
    assert client.post('/shop-login', data=payload).status_code == 302
    # Separate browser, no logout cancellation of the owner's active run.
    member = app.test_client()
    login(member, 'member@example.test')
    assert member.post('/shop-login', data={'csrf_token': csrf(member, '/shop-login'),
        'start_request_id': str(uuid4()), 'cost_consent': 'yes'}).status_code == 409
    with app.app_context():
        run = db.session.scalar(select(ShopLogin))
        run.state, run.active_user_id, run.active_household_id = 'closed', None, None
        db.session.commit()
    assert member.post('/shop-login', data={'csrf_token': csrf(member, '/shop-login'),
        'start_request_id': str(uuid4()), 'cost_consent': 'yes'}).status_code == 302


def test_unbound_household_cannot_queue_account(app, client):
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key')
    login(client, 'other@example.test')
    assert client.get('/shop-login').status_code == 403
    assert client.post('/shop-login', data={'csrf_token': csrf(client, '/'),
        'start_request_id': str(uuid4()), 'cost_consent': 'yes'}).status_code == 403
    with app.app_context():
        assert db.session.scalar(select(ShopLogin)) is None


def test_database_enforces_single_household_account_slot(app, prepared):
    from sqlalchemy.exc import IntegrityError
    identifier, _, _ = prepared
    with app.app_context():
        first = db.session.get(ShopLogin, identifier)
        member = db.session.scalar(select(User).where(User.email == 'member@example.test'))
        db.session.add(ShopLogin(user_id=member.id, household_id=first.household_id,
            auth_version=member.auth_version, expires_at=utcnow() + timedelta(minutes=6)))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_automatic_credentials_use_control_event_without_ui_or_persistence(app, client, prepared):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from james.shop_login_worker import login_handler
    identifier, _, schema = prepared
    schema['fields'][0]['label'] = 'E-Mail'
    api_client = MagicMock()
    approval = SimpleNamespace(request=SimpleNamespace(credential_origin='https://www.galaxus.ch'),
        request_id='request-1', turn_id='turn-1')
    login_handler(app, identifier)(approval, api_client, 'synthetic-session')
    call = api_client.beta.agents.sessions.events.create.call_args
    assert call.args == ('synthetic-session',)
    event = call.kwargs['events'][0]
    assert event['type'] == 'agent.session.input.computer_use_approval_request_result'
    assert event['response']['fields'] == [
        {'field_id': 'email', 'value': 'synthetic-account@example.test'},
        {'field_id': 'password', 'value': 'synthetic-account-password'}]
    with app.app_context():
        run = db.session.get(ShopLogin, identifier)
        assert run.state == 'accepted'
        saved = repr({c.name: getattr(run, c.name) for c in run.__table__.columns})
        assert 'synthetic-account-password' not in saved
    page = client.get(f'/shop-login/{identifier}').data
    assert b'synthetic-account-password' not in page and b'synthetic-account@example.test' not in page


def test_automatic_uncertain_submission_stops_without_retry(app, prepared):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from james.shop_login_worker import login_handler
    identifier, _, schema = prepared
    schema['fields'][0]['label'] = 'E-Mail'
    api_client = MagicMock()
    api_client.beta.agents.sessions.events.create.side_effect = RuntimeError('synthetic-account-password')
    approval = SimpleNamespace(request=SimpleNamespace(credential_origin='https://www.galaxus.ch'),
        request_id='request-1', turn_id='turn-1')
    handler = login_handler(app, identifier)
    with pytest.raises(ValueError, match='keine Wiederholung') as error:
        handler(approval, api_client, 'synthetic-session')
    assert 'synthetic-account-password' not in str(error.value)
    with pytest.raises(ValueError):
        handler(approval, api_client, 'synthetic-session')
    assert api_client.beta.agents.sessions.events.create.call_count == 1
    with app.app_context():
        assert db.session.get(ShopLogin, identifier).state == 'unknown'


def test_mfa_is_manual_and_saved_password_is_never_reused_for_code(app, prepared, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from james.shop_login_worker import login_handler
    identifier, _, schema = prepared
    schema['fields'] = [{'id': 'otp', 'label': 'Bestaetigungscode', 'type': 'password', 'required': True}]
    api_client = MagicMock()
    def user_confirmation(_):
        with app.app_context():
            row = db.session.get(ShopLogin, identifier)
            assert row.state == 'pending'
            row.state = 'accepted'
            db.session.commit()
    monkeypatch.setattr('james.shop_login_worker.Event', lambda: SimpleNamespace(wait=user_confirmation))
    approval = SimpleNamespace(request=SimpleNamespace(credential_origin='https://www.galaxus.ch'),
        request_id='request-1', turn_id='turn-1')
    login_handler(app, identifier)(approval, api_client, 'synthetic-session')
    api_client.beta.agents.sessions.events.create.assert_not_called()


@pytest.mark.parametrize('change', ['household', 'missing_password', 'session', 'cancelled'])
def test_auto_login_rejects_wrong_binding_and_missing_credentials_before_api(app, prepared, monkeypatch, change):
    from unittest.mock import MagicMock
    from james.shop_login_worker import execute_run
    identifier, _, _ = prepared
    client_constructor = MagicMock()
    monkeypatch.setattr('openai.OpenAI', client_constructor)
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.session_id = None
        row.state = 'creating'
        row.cost_authorized_at = utcnow()
        if change == 'household':
            app.config['GALAXUS_HOUSEHOLD_ID'] = '999999'
        elif change == 'missing_password':
            app.config['GALAXUS_PASSWORD'] = ''
        elif change == 'session':
            row.creation_started_at = utcnow()
        else:
            row.state = 'cancelled'
        db.session.commit()
        execute_run(app, identifier)
    client_constructor.assert_not_called()


def test_credential_mapping_handles_split_login_and_never_retries_roles(app):
    from james.shop_account import credential_response
    email = {'id': 'login-email', 'label': 'E-Mail', 'type': 'email', 'required': True}
    password = {'id': 'login-password', 'label': 'Passwort', 'type': 'password', 'required': True}
    schema = {'credential_origin': 'https://www.galaxus.ch', 'fields': [email], 'options': []}
    with app.app_context():
        response, roles = credential_response(schema, app.config, set())
        assert roles == {'email'}
        schema['fields'] = [password]
        _, next_roles = credential_response(schema, app.config, roles)
        assert next_roles == {'password'}
        assert credential_response(schema, app.config, roles | next_roles) is None
        schema['fields'] = [email, password]
        schema['options'] = [{'id': 'existing-account', 'label': 'Anmelden', 'field_ids': ['login-email', 'login-password']}]
        response, _ = credential_response(schema, app.config, set())
        assert response['selected_option'] == 'existing-account'
        schema['options'].append({'id': 'other-method', 'label': 'Andere', 'field_ids': ['login-email', 'login-password']})
        assert credential_response(schema, app.config, set()) is None
        schema['options'] = []
        schema['credential_origin'] = 'https://www.galaxus.ch.evil.example'
        assert credential_response(schema, app.config, set()) is None


@pytest.mark.parametrize('field', [
    {'id': 'otp', 'label': 'Einmalpasswort', 'type': 'password', 'required': True},
    {'id': 'new', 'label': 'Neues Passwort', 'type': 'password', 'required': True},
    {'id': 'consent', 'label': 'Passwort', 'type': 'checkbox', 'required': True},
    {'id': 'unknown', 'label': 'Unbekannt', 'type': 'text', 'required': True},
])
def test_unrecognised_fields_cannot_receive_server_secret(app, field):
    from james.shop_account import credential_response
    with app.app_context():
        assert credential_response({'credential_origin': 'https://www.galaxus.ch',
            'fields': [field], 'options': []}, app.config, set()) is None


def test_old_closed_test_does_not_claim_success(client, app, prepared):
    identifier, _, _ = prepared
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.state, row.active_user_id, row.active_household_id = 'closed', None, None
        db.session.commit()
    page = client.get(f'/shop-login/{identifier}').text
    assert 'kein genauer Ergebnisnachweis' in page
    assert 'erfolgreicher Login ist nicht bestätigt' in page
    assert 'beendet oder wurde abgebrochen' not in page


def test_executor_preserves_failure_details_after_successful_cleanup(app, client, prepared, monkeypatch, capsys):
    from unittest.mock import MagicMock
    from james.shop_login_worker import execute_run
    identifier, _, _ = prepared
    monkeypatch.setattr('openai.OpenAI', MagicMock())
    def fake_run(client, url, path, **options):
        options['session_handler']('synthetic-created-session')
        return {'status': 'failed', 'cleanup': 'deleted', 'http_status': 403, 'browser_calls': 0,
            'error_type': 'PermissionDeniedError', 'model_report': 'private-page-content',
            'error_code': 'synthetic-account-password', 'error_param': 'synthetic-account@example.test'}
    monkeypatch.setattr('scripts.jayjay_browser_probe.run_task', fake_run)
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.session_id, row.state, row.cost_authorized_at = None, 'creating', utcnow()
        db.session.commit()
        execute_run(app, identifier)
        db.session.expire_all()
        row = db.session.get(ShopLogin, identifier)
        assert row.state == 'closed' and row.active_household_id is None
        assert (row.outcome, row.http_status, row.browser_calls, row.error_category) == ('failed', 403, 0, 'api')
        persisted = repr({c.name: getattr(row, c.name) for c in row.__table__.columns})
    page = client.get(f'/shop-login/{identifier}').text
    logs = capsys.readouterr().out
    for secret in ('synthetic-account-password', 'synthetic-account@example.test', 'private-page-content'):
        assert secret not in persisted and secret not in page and secret not in logs
    assert 'HTTP 403' in page and 'Browserauftrag ist fehlgeschlagen' in page
    assert 'Bereinigung dieses Tests ist abgeschlossen' in page
    assert 'HTTP: 403' in logs


@pytest.mark.parametrize('result,outcome,error', [
    ({'status': 'timeout', 'browser_calls': 12}, 'timeout', None),
    ({'status': 'turn_completed'}, 'no_authentication', None),
    ({'status': 'failed', 'failure_stage': 'environment_failed'}, 'failed', 'environment_failed'),
    ({'status': 'failed', 'error_type': 'APIConnectionError'}, 'failed', 'connection'),
    ({'status': 'failed', 'error_type': 'private-secret'}, 'failed', 'internal'),
    ({'status': ['private-secret'], 'http_status': True, 'browser_calls': -1}, 'failed', None),
])
def test_only_safe_result_metadata_is_retained(app, prepared, result, outcome, error):
    from james.shop_login_worker import save_result
    identifier, _, _ = prepared
    with app.app_context():
        save_result(identifier, result)
        row = db.session.get(ShopLogin, identifier)
        assert row.outcome == outcome and row.error_category == error
        if type(result.get('http_status')) is not int:
            assert row.http_status is None
        assert 'private-secret' not in repr({c.name: getattr(row, c.name) for c in row.__table__.columns})


def test_cleanup_retains_user_cancellation_reason(app, prepared):
    identifier, _, _ = prepared
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.state, row.session_id = 'cancelled', None
        db.session.commit()
        assert cleanup(identifier)
        row = db.session.get(ShopLogin, identifier)
        assert row.state == 'closed' and row.outcome == 'cancelled'


def test_no_authentication_is_not_hidden_by_normal_turn_completion(app, client, prepared):
    from james.shop_login_worker import save_result
    identifier, _, _ = prepared
    with app.app_context():
        save_result(identifier, {'status': 'turn_completed', 'browser_calls': 5,
            'login_report': 'auth_unavailable', 'model_report': 'synthetic-account-password'})
        row = db.session.get(ShopLogin, identifier)
        assert row.outcome == 'no_authentication'
        assert row.auth_progress == 'agent_auth_unavailable'
        row.state, row.active_user_id, row.active_household_id = 'closed', None, None
        db.session.commit()
    page = client.get(f'/shop-login/{identifier}').text
    assert 'ohne registrierte Anmeldeanforderung' in page
    assert 'Ungeprüfte Agentenmeldung' in page and 'nicht verfügbar' in page
    assert 'synthetic-account-password' not in page


def test_agent_report_cannot_replace_observed_authentication(app, prepared):
    from james.shop_login_worker import save_result
    identifier, _, _ = prepared
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.auth_progress = 'credentials_submitted'
        db.session.commit()
        save_result(identifier, {'status': 'turn_completed', 'browser_calls': 5, 'login_report': 'access_blocked'})
        row = db.session.get(ShopLogin, identifier)
        assert row.outcome == 'turn_completed' and row.auth_progress == 'credentials_submitted'


def test_old_completed_run_without_authentication_is_explicit(app, client, prepared):
    identifier, _, _ = prepared
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.state, row.active_user_id, row.active_household_id = 'closed', None, None
        row.outcome, row.browser_calls = 'turn_completed', 5
        db.session.commit()
    page = client.get(f'/shop-login/{identifier}').text
    assert 'ohne registrierte Anmeldeanforderung' in page
    assert 'hinterlegten Zugangsdaten wurde nicht ausgeführt' in page


def test_untrusted_report_is_not_stored(app, prepared):
    from james.shop_login_worker import save_result
    identifier, _, _ = prepared
    with app.app_context():
        save_result(identifier, {'status': 'turn_completed', 'browser_calls': 5,
            'login_report': 'private-secret', 'model_report': 'private-secret'})
        row = db.session.get(ShopLogin, identifier)
        assert row.outcome == 'no_authentication' and row.auth_progress is None
        assert 'private-secret' not in repr({c.name: getattr(row, c.name) for c in row.__table__.columns})


def test_signed_in_claim_without_authentication_is_not_login_success(app, client, prepared):
    from james.shop_login_worker import save_result
    identifier, _, _ = prepared
    with app.app_context():
        save_result(identifier, {'status': 'turn_completed', 'browser_calls': 5, 'login_report': 'signed_in'})
        row = db.session.get(ShopLogin, identifier)
        assert row.outcome == 'no_authentication' and row.auth_progress == 'agent_signed_in'
        row.state, row.active_user_id, row.active_household_id = 'closed', None, None
        db.session.commit()
    page = client.get(f'/shop-login/{identifier}').text
    assert 'ohne registrierte Anmeldeanforderung' in page
    assert 'Ungeprüfte Agentenmeldung' in page and 'kein Nachweis' in page


def test_observed_origin_denial_takes_precedence_over_agent_guess(app, prepared):
    from james.shop_login_worker import save_result
    identifier, _, _ = prepared
    with app.app_context():
        save_result(identifier, {'status': 'turn_completed', 'browser_calls': 5,
            'origin_access_denied': True, 'login_report': 'access_blocked'})
        row = db.session.get(ShopLogin, identifier)
        assert row.outcome == 'no_authentication' and row.auth_progress == 'origin_denied'


def test_verified_galaxus_identity_origin_supports_registered_authentication(app, client, prepared):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from james.shop_login_worker import login_handler
    identifier, _, schema = prepared
    schema['credential_origin'] = 'https://id.digitecgalaxus.ch'
    schema['fields'][0]['label'] = 'E-Mail'
    page = client.get(f'/shop-login/{identifier}')
    assert page.status_code == 200 and b'https://id.digitecgalaxus.ch' in page.data
    api_client = MagicMock()
    approval = SimpleNamespace(request=SimpleNamespace(credential_origin='https://id.digitecgalaxus.ch'),
        request_id='request-1', turn_id='turn-1')
    login_handler(app, identifier)(approval, api_client, 'synthetic-session')
    api_client.beta.agents.sessions.events.create.assert_called_once()
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        assert row.auth_progress == 'both_submitted'


@pytest.mark.parametrize('origin', ['https://id.digitecgalaxus.ch.evil.example',
    'https://digitecgalaxus.ch', 'https://id.digitecgalaxus.ch:8443'])
def test_identity_lookalikes_cannot_receive_credentials(app, client, prepared, origin):
    from james.shop_account import credential_response
    identifier, calls, schema = prepared
    schema['credential_origin'] = origin
    schema['fields'][0]['label'] = 'E-Mail'
    assert client.get(f'/shop-login/{identifier}').status_code == 410
    with app.app_context():
        assert credential_response(schema, app.config, set()) is None
    assert not [call for call in calls if call[0] == 'POST']


def test_cart_mode_requires_separate_consent_and_cannot_repurpose_request(app, client):
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key')
    login(client)
    data = {'csrf_token': csrf(client, '/shop-login'), 'start_request_id': str(uuid4()),
        'cost_consent': 'yes', 'task_kind': 'cart'}
    assert client.post('/shop-login', data=data).status_code == 400
    with app.app_context():
        assert db.session.scalar(select(ShopLogin)) is None
    data['cart_consent'] = 'yes'
    response = client.post('/shop-login', data=data)
    assert response.status_code == 302
    assert client.post('/shop-login', data=data).location == response.location
    assert client.post('/shop-login', data={**data, 'task_kind': 'login'}).status_code == 409
    with app.app_context():
        row = db.session.scalar(select(ShopLogin))
        assert row.task_kind == 'cart' and row.cost_authorized_at


def test_one_cart_attempt_per_household_day_does_not_change_login_limit(app, client):
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key')
    login(client)
    # Two existing completed login attempts must not consume the one separately consented cart proof.
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == 'owner@example.test'))
        home = app.config['GALAXUS_HOUSEHOLD_ID']
        for _ in range(2):
            db.session.add(ShopLogin(user_id=user.id, household_id=int(home), auth_version=user.auth_version,
                task_kind='login', state='closed', active_user_id=None, active_household_id=None,
                expires_at=utcnow()))
            db.session.flush()
            row = db.session.scalar(select(ShopLogin).order_by(ShopLogin.id.desc()))
            row.active_user_id, row.active_household_id = None, None
        db.session.commit()
    data = {'csrf_token': csrf(client, '/shop-login'), 'start_request_id': str(uuid4()),
        'cost_consent': 'yes', 'task_kind': 'cart', 'cart_consent': 'yes'}
    assert client.post('/shop-login', data=data).status_code == 302
    with app.app_context():
        row = db.session.scalar(select(ShopLogin).where(ShopLogin.task_kind == 'cart'))
        row.state, row.active_user_id, row.active_household_id = 'closed', None, None
        db.session.commit()
    assert client.post('/shop-login', data={**data, 'start_request_id': str(uuid4())}).status_code == 409


def test_cart_executor_uses_fixed_target_plan_and_keeps_unverified_report(app, prepared, monkeypatch):
    from unittest.mock import MagicMock
    from james.shop_login_worker import execute_run
    identifier, _, _ = prepared
    monkeypatch.setattr('openai.OpenAI', MagicMock())
    def fake_run(client, url, path, **options):
        options['session_handler']('synthetic-cart-session')
        assert options['authentication_handler'] is not None
        assert '14684120' in options['instructions'] and '14730798' in options['instructions'] and '37264242' in options['instructions']
        assert options['authorized_uncapped_test'] is True
        assert options['additional_allowed_origins'] == ('https://id.digitecgalaxus.ch',)
        assert 'screenshot_path' not in options
        with app.app_context():
            row = db.session.get(ShopLogin, identifier)
            row.auth_progress = 'credentials_submitted'
            db.session.commit()
        return {'status': 'turn_completed', 'browser_calls': 30, 'cleanup': 'deleted', 'login_report': 'cart_ready'}
    monkeypatch.setattr('scripts.jayjay_browser_probe.run_task', fake_run)
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.session_id, row.state, row.task_kind, row.cost_authorized_at = None, 'creating', 'cart', utcnow()
        db.session.commit()
        execute_run(app, identifier)
        db.session.expire_all()
        row = db.session.get(ShopLogin, identifier)
        assert row.state == 'closed' and row.agent_report == 'cart_ready'
        assert row.device_verified_at is None


def test_cart_ready_claim_without_auth_is_not_accepted(app, prepared):
    from james.shop_login_worker import save_result
    identifier, _, _ = prepared
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.task_kind = 'cart'
        db.session.commit()
        save_result(identifier, {'status': 'turn_completed', 'browser_calls': 5, 'login_report': 'cart_ready'})
        row = db.session.get(ShopLogin, identifier)
        assert row.agent_report == 'account_not_verified' and row.device_verified_at is None
        assert row.outcome == 'no_authentication'


def test_device_verification_is_private_explicit_idempotent_and_does_not_call_api(app, client, prepared, monkeypatch):
    identifier, _, _ = prepared
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.task_kind, row.state, row.active_user_id, row.active_household_id = 'cart', 'closed', None, None
        db.session.commit()
    monkeypatch.setattr('james.shop_login.api', lambda *a: pytest.fail('Device confirmation must not call API'))
    path = f'/shop-login/{identifier}'
    payload = {'csrf_token': csrf(client, path), 'action': 'verify_cart'}
    assert client.post(path, data=payload).status_code == 400
    payload['cart_verified'] = 'yes'
    assert client.post(path, data=payload).status_code == 302
    with app.app_context():
        first = db.session.get(ShopLogin, identifier).device_verified_at
        assert first is not None
    assert client.post(path, data=payload).status_code == 302
    with app.app_context():
        assert db.session.get(ShopLogin, identifier).device_verified_at == first
    assert 'Von dir auf deinem Gerät bestätigt' in client.get(path).text
    member = app.test_client()
    login(member, 'member@example.test')
    assert member.post(path, data={'csrf_token': csrf(member, '/'), 'action': 'verify_cart', 'cart_verified': 'yes'}).status_code == 404


def test_device_confirmation_rejects_login_mode_and_unfinished_cart(app, client, prepared):
    identifier, _, _ = prepared
    path = f'/shop-login/{identifier}'
    payload = {'csrf_token': csrf(client, path), 'action': 'verify_cart', 'cart_verified': 'yes'}
    assert client.post(path, data=payload).status_code == 409
    with app.app_context():
        db.session.get(ShopLogin, identifier).task_kind = 'cart'
        db.session.commit()
    assert client.post(path, data=payload).status_code == 409


def test_disabled_cart_mode_cannot_be_queued_or_executed(app, client, prepared, monkeypatch):
    from unittest.mock import MagicMock
    from james.shop_login_worker import execute_run
    identifier, _, _ = prepared
    app.config['SHOP_CART_PILOT_ENABLED'] = False
    assert 'value="cart"' not in client.get('/shop-login').text
    assert client.post('/shop-login', data={'csrf_token': csrf(client, '/shop-login'),
        'start_request_id': str(uuid4()), 'task_kind': 'cart', 'cost_consent': 'yes',
        'cart_consent': 'yes'}).status_code == 404
    constructor = MagicMock()
    monkeypatch.setattr('openai.OpenAI', constructor)
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.task_kind, row.state, row.session_id, row.cost_authorized_at = 'cart', 'creating', None, utcnow()
        db.session.commit()
        execute_run(app, identifier)
        assert db.session.get(ShopLogin, identifier).outcome == 'disabled'
    constructor.assert_not_called()


def test_extra_cart_attempt_is_date_bound_and_never_unlimited(app, monkeypatch):
    from datetime import datetime
    from james.shop_login import cart_daily_limit
    fixed = datetime(2026, 11, 3, 12)
    monkeypatch.setattr('james.shop_login.utcnow', lambda: fixed)
    with app.app_context():
        for value in ('', None, 'bad', '2026-11-02', '2026-11-04'):
            app.config['SHOP_CART_EXTRA_ATTEMPT_DATE'] = value
            assert cart_daily_limit() == 1
        app.config['SHOP_CART_EXTRA_ATTEMPT_DATE'] = '2026-11-03'
        assert cart_daily_limit() == 2
        monkeypatch.setattr('james.shop_login.utcnow', lambda: datetime(2026, 11, 4, 0))
        assert cart_daily_limit() == 1


def test_extra_attempt_requires_fresh_consent_and_stops_after_two(app, client, monkeypatch):
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key',
        SHOP_CART_EXTRA_ATTEMPT_DATE=utcnow().date().isoformat())
    login(client)
    monkeypatch.setattr('james.shop_login.api', lambda *a: pytest.fail('Queueing must never start a paid session'))
    assert 'zusätzlicher Warenkorbversuch' in client.get('/shop-login').text
    data = {'csrf_token': csrf(client, '/shop-login'), 'task_kind': 'cart', 'cart_consent': 'yes'}
    assert client.post('/shop-login', data={**data, 'start_request_id': str(uuid4())}).status_code == 400
    data['cost_consent'] = 'yes'
    first_id = None
    for _ in range(2):
        request_id = str(uuid4())
        response = client.post('/shop-login', data={**data, 'start_request_id': request_id})
        assert response.status_code == 302
        first_id = first_id or request_id
        with app.app_context():
            row = db.session.scalar(select(ShopLogin).where(ShopLogin.start_request_id == request_id))
            row.state, row.active_user_id, row.active_household_id = 'closed', None, None
            db.session.commit()
    assert client.post('/shop-login', data={**data, 'start_request_id': str(uuid4())}).status_code == 409
    # Replaying an already consumed request remains idempotent, never a third execution.
    assert client.post('/shop-login', data={**data, 'start_request_id': first_id}).status_code == 302
    with app.app_context():
        assert len(db.session.scalars(select(ShopLogin)).all()) == 2


@pytest.mark.parametrize('repeat_email', [False, True])
def test_multistep_handler_preserves_progress_and_submits_first_password(app, prepared, monkeypatch, repeat_email):
    from types import SimpleNamespace as NS
    from unittest.mock import MagicMock
    from james.shop_login_worker import login_handler
    identifier, _, schema = prepared
    email = {'id': 'email', 'label': 'E-Mail', 'type': 'email', 'required': True}
    password = {'id': 'password', 'label': 'Passwort', 'type': 'password', 'required': True}
    schema['fields'] = [email]
    monkeypatch.setattr('james.shop_login_worker.challenge', lambda run: schema)
    handler = login_handler(app, identifier)
    api_client = MagicMock()
    def stage(request_id):
        handler(NS(request=NS(credential_origin='https://www.galaxus.ch'),
            request_id=request_id, turn_id='turn-1'), api_client, 'synthetic-session')
    stage('email-step')
    with app.app_context():
        assert db.session.get(ShopLogin, identifier).auth_progress == 'email_submitted'
    schema['fields'] = [email, password] if repeat_email else [password]
    stage('password-step')
    with app.app_context():
        assert db.session.get(ShopLogin, identifier).auth_progress == 'both_submitted'
    calls = api_client.beta.agents.sessions.events.create.call_args_list
    assert len(calls) == 2
    assert calls[1].kwargs['events'][0]['request_id'] == 'password-step'
    assert any(f['field_id'] == 'password' for f in calls[1].kwargs['events'][0]['response']['fields'])


def test_second_password_and_email_only_retry_still_require_manual_input(app):
    from james.shop_account import credential_response
    email = {'id': 'email', 'label': 'E-Mail', 'type': 'email', 'required': True}
    password = {'id': 'password', 'label': 'Passwort', 'type': 'password', 'required': True}
    for fields, used in [([email], {'email'}), ([password], {'password'}),
                          ([email, password], {'email', 'password'}), ([email, password], {'password'})]:
        assert credential_response({'credential_origin': 'https://www.galaxus.ch',
            'fields': fields, 'options': []}, app.config, used) is None


def test_status_poll_is_private_read_only_and_does_not_fetch_credentials(app, client, prepared, monkeypatch):
    identifier, _, _ = prepared
    monkeypatch.setattr('james.shop_login.api', lambda *a: pytest.fail('status must not fetch authentication'))
    result = client.get(f'/shop-login/{identifier}/status')
    assert result.status_code == 200
    assert result.json == {'state': 'pending', 'progress': ''}
    assert result.headers['Cache-Control'] == 'no-store'
    other = app.test_client()
    login(other, 'member@example.test')
    assert other.get(f'/shop-login/{identifier}/status').status_code == 404


def test_status_poll_stops_on_manual_form_and_does_not_claim_password_sent(app, client, prepared):
    identifier, _, _ = prepared
    assert b'shop-login-status.js' not in client.get(f'/shop-login/{identifier}').data
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.state, row.auth_progress, row.outcome = 'accepted', 'email_submitted', 'turn_completed'
        db.session.commit()
    page = client.get(f'/shop-login/{identifier}').data.decode()
    assert 'shop-login-status.js' in page
    assert 'nur die E-Mail' in page
    assert 'E-Mail und Passwort wurden' not in page


@pytest.mark.parametrize('report', ['login_rejected', 'verification_required', 'login_incomplete', 'redirect_pending'])
def test_precise_login_failure_is_retained_for_login_and_cart(app, prepared, report):
    from james.shop_login_worker import save_result
    identifier, _, _ = prepared
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.auth_progress = 'email_submitted'
        for kind in ('login', 'cart'):
            row.task_kind = kind
            db.session.commit()
            save_result(identifier, {'status': 'turn_completed', 'login_report': report})
            assert row.agent_report == report


def test_expired_watchdog_cancellation_is_not_generic_failure(app, prepared):
    from james.shop_login_worker import cancellation_reason, save_result
    identifier, _, _ = prepared
    with app.app_context():
        row = db.session.get(ShopLogin, identifier)
        row.state = 'accepted'
        row.expires_at = utcnow() - timedelta(seconds=1)
        row.auth_progress = 'email_submitted'
        db.session.commit()
        assert cancellation_reason(row) == 'deadline_expired'
        save_result(identifier, {'status': 'failed', 'failure_stage': 'turn_cancelled', 'local_cancel_reason': 'deadline_expired'})
        assert row.outcome == 'expired'
        assert row.auth_progress == 'email_submitted'
        row.state = 'cancelled'
        db.session.commit()
        assert cancellation_reason(row) == 'cancelled'
        save_result(identifier, {'status': 'failed', 'failure_stage': 'turn_cancelled', 'local_cancel_reason': 'deadline_expired'})
        assert row.outcome == 'cancelled'


def test_new_deadline_is_disclosed_and_bounded_from_user_submission(app, client):
    from james.shop_limits import SHOP_TEST_SECONDS
    app.config.update(SHOP_LOGIN_PILOT_ENABLED=True, OPENAI_API_KEY='synthetic-only-key')
    login(client)
    page = client.get('/shop-login').data.decode()
    assert f'Nach {SHOP_TEST_SECONDS // 60} Minuten' in page
    before = utcnow()
    response = client.post('/shop-login', data={'csrf_token': csrf(client, '/shop-login'),
        'start_request_id': str(uuid4()), 'cost_consent': 'yes'})
    assert response.status_code == 302
    with app.app_context():
        row = db.session.scalar(select(ShopLogin))
        assert before + timedelta(seconds=SHOP_TEST_SECONDS) <= row.expires_at <= utcnow() + timedelta(seconds=SHOP_TEST_SECONDS)
