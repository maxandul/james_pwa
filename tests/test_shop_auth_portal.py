from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from time import monotonic
from types import SimpleNamespace as NS
from unittest.mock import MagicMock

import pytest

spec = spec_from_file_location('shop_auth_portal', Path(__file__).parents[1] / 'scripts/shop_auth_portal.py')
module = module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def portal():
    portal = module.LoginPortal('https://www.galaxus.ch')
    portal.origin = 'http://127.0.0.1:8765'
    fields = [NS(id='email', label='<script>unsafe</script>', required=True, type='email'),
              NS(id='password', label='Passwort', required=True, type='password')]
    approval = NS(type='computer_use_approval_request', request_id='request-1', turn_id='turn-1',
        request=NS(type='browser_authentication', credential_origin='https://www.galaxus.ch',
                   fields=fields, options=[]))
    api = MagicMock()
    api.beta.agents.sessions.retrieve.return_value = NS(status='requires_action', required_actions=[approval])
    portal.pending = (approval, api, 'synthetic-session')
    portal.deadline = monotonic() + 60
    return portal, portal.app.test_client(), api, approval


def post(portal, client, **changes):
    data = {'csrf': portal.csrf, 'request_id': 'request-1', 'option': '',
        'destination_confirmed': 'yes', 'action': 'submit',
        'value_0': 'synthetic@example.test', 'value_1': 'synthetic-private-value'}
    data.update(changes)
    return client.post('/' + portal.token, data=data, base_url=portal.origin,
                       headers={'Origin': portal.origin})


def test_form_escapes_metadata_and_has_no_store_or_external_resources(portal):
    p, client, api, _ = portal
    response = client.get('/' + p.token, base_url=p.origin)
    assert response.status_code == 200
    assert b'&lt;script&gt;unsafe&lt;/script&gt;' in response.data
    assert b'type="password"' in response.data
    assert response.headers['Cache-Control'] == 'no-store'
    assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
    api.beta.agents.sessions.events.create.assert_not_called()


def test_submit_uses_current_request_and_does_not_echo_or_retain_values(portal):
    p, client, api, _ = portal
    response = post(p, client)
    assert response.status_code == 200
    event = api.beta.agents.sessions.events.create.call_args.kwargs['events'][0]
    assert event['request_id'] == 'request-1'
    assert event['response']['fields'] == [
        {'field_id': 'email', 'value': 'synthetic@example.test'},
        {'field_id': 'password', 'value': 'synthetic-private-value'}]
    assert b'synthetic-private-value' not in response.data
    assert b'synthetic@example.test' not in response.data
    assert p.pending is None
    assert p.outcome == 'accepted'
    assert 'synthetic-private-value' not in repr(p.__dict__)
    assert post(p, client).status_code == 410
    assert api.beta.agents.sessions.events.create.call_count == 1


@pytest.mark.parametrize('changes,status', [
    ({'csrf': 'bad'}, 403), ({'request_id': 'stale'}, 409),
    ({'csrf': '\u2603'}, 403),
    ({'destination_confirmed': ''}, 400), ({'value_1': ''}, 400),
    ({'value_2': 'unexpected'}, 400), ({'option': 'unknown'}, 400),
])
def test_invalid_submission_never_reaches_api(portal, changes, status):
    p, client, api, _ = portal
    assert post(p, client, **changes).status_code == status
    api.beta.agents.sessions.events.create.assert_not_called()


def test_cross_origin_and_wrong_host_are_rejected(portal):
    p, client, api, _ = portal
    assert client.post('/' + p.token, base_url=p.origin,
        headers={'Origin': 'https://other.example'}, data={'csrf': p.csrf}).status_code == 403
    assert client.get('/' + p.token, base_url='http://attacker.example:8765').status_code == 403
    api.beta.agents.sessions.events.create.assert_not_called()


def test_expired_or_changed_upstream_challenge_never_receives_credentials(portal):
    p, client, api, _ = portal
    api.beta.agents.sessions.retrieve.return_value = NS(status='idle', required_actions=[])
    assert post(p, client).status_code == 410
    api.beta.agents.sessions.events.create.assert_not_called()
    p.deadline = monotonic() - 1
    assert post(p, client).status_code == 410


def test_uncertain_submission_is_closed_without_secret_error_or_retry(portal):
    p, client, api, _ = portal
    api.beta.agents.sessions.events.create.side_effect = RuntimeError('synthetic-private-value')
    response = post(p, client)
    assert response.status_code == 409
    assert p.outcome == 'uncertain'
    assert b'synthetic-private-value' not in response.data
    assert post(p, client).status_code == 410
    assert api.beta.agents.sessions.events.create.call_count == 1


def test_login_method_limits_submitted_fields(portal):
    p, client, api, approval = portal
    approval.request.options = [NS(id='email-only', label='Code per E-Mail', field_ids=['email'])]
    assert post(p, client, option='email-only').status_code == 400  # Extraneous password field.
    response = client.post('/' + p.token, base_url=p.origin, headers={'Origin': p.origin}, data={
        'csrf': p.csrf, 'request_id': 'request-1', 'option': 'email-only',
        'action': 'submit', 'destination_confirmed': 'yes', 'value_0': 'synthetic@example.test'})
    assert response.status_code == 200
    result = api.beta.agents.sessions.events.create.call_args.kwargs['events'][0]['response']
    assert result['selected_option'] == 'email-only'
    assert result['fields'] == [{'field_id': 'email', 'value': 'synthetic@example.test'}]


def test_unrecognized_credential_origin_is_rejected_before_prompt(portal):
    p, _, api, approval = portal
    approval.request.credential_origin = 'https://www.galaxus.ch.evil.example'
    with pytest.raises(ValueError):
        p.handle(approval, api, 'synthetic-session')
    api.with_options.assert_not_called()
