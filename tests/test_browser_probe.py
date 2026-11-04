"""Probe boundaries and uncertain outcomes; no API calls or shop data."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock

import pytest

spec = spec_from_file_location('browser_probe', Path(__file__).parents[1] / 'scripts/jayjay_browser_probe.py')
module = module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('url', [
    'http://www.coop.ch', 'https://user:secret@www.coop.ch',
    'https://127.0.0.1', 'https://localhost', 'https://host.local',
    'https://www.coop.ch:8443',
])
def test_reject_non_public_or_credential_urls(url):
    with pytest.raises(ValueError):
        module.origin_for(url)


def test_exact_origin_and_authentication_boundaries():
    assert module.origin_for('https://WWW.COOP.CH/de/p/3032108') == 'https://www.coop.ch'
    for origin, decision in [('https://www.coop.ch', 'approve'),
                             ('https://www.coop.ch.evil.test', 'deny'),
                             ('https://login.coop.ch', 'deny')]:
        assert module.approval_response(NS(type='browser_origin_access', origin=origin),
            'https://www.coop.ch')['decision'] == decision
    assert module.approval_response(NS(type='browser_authentication'),
        'https://www.coop.ch') == {'type': 'browser_authentication', 'action': 'cancel'}


def fake_client(events):
    client = MagicMock()
    sessions = client.beta.agents.sessions
    sessions.create.return_value = NS(id='synthetic-session', spend_control=NS(limit=300))
    sessions.events.stream.return_value.__enter__.return_value = iter(events)
    return client, sessions


def test_disconnect_never_replays_and_deletes_session(tmp_path):
    client, sessions = fake_client([])
    state = tmp_path / 'state.json'
    result = module.probe(client, 'https://www.coop.ch/de/p/3032108', state)
    assert result['status'] == 'disconnected'
    assert result['cleanup'] == 'deleted'
    sessions.events.create.assert_called_once()
    sessions.delete.assert_called_once_with('synthetic-session')
    assert state.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        module.probe(client, 'https://www.coop.ch/de/p/3032108', state)
    assert sessions.create.call_count == 1


def test_completion_text_alone_is_not_browser_evidence(tmp_path):
    client, _ = fake_client([
        NS(type='agent.session.turn.output_text.done', text='Product found'),
        NS(type='agent.session.turn.completed', turn=NS(subagent_id=None)),
    ])
    result = module.probe(client, 'https://www.coop.ch/de/p/3032108', tmp_path / 'state.json')
    assert result['status'] == 'no_browser_evidence'


def test_preserves_browser_screenshot_separately_from_model_claim(tmp_path):
    client, _ = fake_client([
        NS(type='agent.session.turn.item.done', item=NS(type='computer_use_call',
            output=NS(type='computer_screenshot', image_url='data:image/png;base64,cGl4ZWxz'))),
        NS(type='agent.session.turn.completed', turn=NS(subagent_id=None)),
    ])
    screenshot = tmp_path / 'public.png'
    result = module.probe(client, 'https://www.coop.ch/de/p/3032108',
        tmp_path / 'state.json', screenshot_path=screenshot)
    assert result['status'] == 'turn_completed'
    assert result['screenshots'] == 1
    assert screenshot.read_bytes() == b'pixels'


def test_uncertain_submission_not_retried_and_error_is_redacted(tmp_path):
    client, sessions = fake_client([])
    sessions.events.create.side_effect = RuntimeError('secret-request-material')
    result = module.probe(client, 'https://www.coop.ch/de/p/3032108', tmp_path / 'state.json')
    assert result['status'] == 'failed'
    assert result['error_type'] == 'RuntimeError'
    assert 'secret-request-material' not in str(result)
    assert [c.kwargs['events'][0]['type'] for c in sessions.events.create.call_args_list] == [
        'agent.session.input.message', 'agent.session.input.cancel']
    sessions.delete.assert_called_once()


def test_cleanup_failure_keeps_session_id_for_operator(tmp_path):
    client, sessions = fake_client([])
    sessions.delete.side_effect = RuntimeError('secret')
    state = tmp_path / 'state.json'
    result = module.probe(client, 'https://www.coop.ch/de/p/3032108', state)
    assert result['cleanup'] == 'pending'
    assert 'synthetic-session' in state.read_text()
    assert 'secret' not in state.read_text()


def test_guest_cart_session_is_retained_and_reused_without_new_creation(tmp_path):
    client, sessions = fake_client([
        NS(type='agent.session.turn.completed', turn=NS(subagent_id=None)),
    ])
    sessions.retrieve.return_value = NS(status='idle', required_actions=[], spend_control=NS(limit=300))
    result = module.run_task(client, 'https://www.galaxus.ch', tmp_path / 'repeat.json',
        instructions='test', task='verify only', session_id='existing-test-session', keep_session=True)
    assert result['cleanup'] == 'retained'
    sessions.create.assert_not_called()
    sessions.delete.assert_not_called()
    sessions.events.create.assert_called_once()


@pytest.mark.parametrize('keep_session', [False, True])
def test_missing_spending_limit_never_sends_task(tmp_path, keep_session):
    client, sessions = fake_client([])
    sessions.create.return_value = NS(id='synthetic-session', spend_control=None)
    result = module.run_task(client, 'https://www.galaxus.ch', tmp_path / 'uncapped.json',
        instructions='test', task='must not be sent', keep_session=keep_session)
    assert result['status'] == 'failed'
    sessions.events.create.assert_not_called()
    sessions.delete.assert_called_once_with('synthetic-session')


def test_busy_session_is_inspected_without_resending_or_deleting(tmp_path):
    client, sessions = fake_client([])
    sessions.retrieve.return_value = NS(status='in_progress', required_actions=[])
    result = module.run_task(client, 'https://www.galaxus.ch', tmp_path / 'busy.json',
        instructions='test', task='must not be sent', session_id='existing-test-session', keep_session=True)
    assert result['status'] == 'failed'
    assert result['cleanup'] == 'retained'
    sessions.events.create.assert_not_called()
    sessions.create.assert_not_called()
    sessions.delete.assert_not_called()


def test_explicit_single_test_authorization_never_retains_uncapped_session(tmp_path):
    client, sessions = fake_client([])
    sessions.create.return_value = NS(id='synthetic-session', spend_control=None)
    result = module.run_task(client, 'https://www.galaxus.ch', tmp_path / 'authorized.json',
        instructions='test', task='single test', seconds=720, authorized_uncapped_test=True)
    assert result['cost_control'] == 'explicit_uncapped_single_test'
    assert result['cleanup'] == 'deleted'
    assert 'spend_control' not in sessions.create.call_args.kwargs
    sessions.events.create.assert_called_once()
    sessions.delete.assert_called_once_with('synthetic-session')


@pytest.mark.parametrize('options', [
    {'keep_session': True}, {'session_id': 'existing'}, {'seconds': 721},
])
def test_uncapped_authorization_cannot_expand_into_persistent_or_longer_run(tmp_path, options):
    client, sessions = fake_client([])
    with pytest.raises(ValueError):
        module.run_task(client, 'https://www.galaxus.ch', tmp_path / 'invalid.json',
            instructions='test', task='never send', authorized_uncapped_test=True, **options)
    sessions.create.assert_not_called()
    sessions.events.create.assert_not_called()


def test_auth_mode_never_persists_private_model_text(tmp_path):
    client, sessions = fake_client([
        NS(type='agent.session.turn.output_text.done', text='synthetic-private-account'),
        NS(type='agent.session.turn.completed', turn=NS(subagent_id=None)),
    ])
    state = tmp_path / 'login.json'
    result = module.run_task(client, 'https://www.galaxus.ch', state,
        instructions='test', task='login', authentication_handler=lambda *args: None)
    assert result['model_report'] == ''
    assert 'synthetic-private-account' not in state.read_text()


def test_auth_mode_rejects_disk_screenshot_before_creating_session(tmp_path):
    client, sessions = fake_client([])
    with pytest.raises(ValueError):
        module.run_task(client, 'https://www.galaxus.ch', tmp_path / 'login.json',
            instructions='test', task='login', authentication_handler=lambda *args: None,
            screenshot_path=tmp_path / 'private.jpg')
    sessions.create.assert_not_called()


@pytest.mark.parametrize('event_type,stage', [
    ('agent.session.environment.failed', 'environment_failed'),
    ('agent.session.failed', 'agent_failed'),
    ('agent.session.turn.failed', 'turn_failed'),
    ('agent.session.turn.cancelled', 'turn_cancelled'),
])
def test_terminal_failure_stage_is_fixed_metadata_only(tmp_path, event_type, stage):
    client, _ = fake_client([NS(type=event_type, turn=NS(subagent_id=None), message='private-secret')])
    result = module.run_task(client, 'https://www.galaxus.ch', tmp_path / 'failure.json',
        instructions='test', task='test only', authentication_handler=lambda *args: None)
    assert result['status'] == 'failed' and result['failure_stage'] == stage
    assert result['cleanup'] == 'deleted'
    assert 'private-secret' not in str(result)


@pytest.mark.parametrize('text', [
    'JAMES_LOGIN_REPORT=ACCESS_BLOCKED secret-password',
    'Some private text: JAMES_LOGIN_REPORT=ACCESS_BLOCKED',
    'JAMES_LOGIN_REPORT=private-password', 'private-password', 'x' * 1000, None,
])
def test_login_report_rejects_free_text_and_unknown_values(text):
    assert module.login_report(text) is None


@pytest.mark.parametrize('token,value', list(module.LOGIN_REPORTS.items()))
def test_login_report_accepts_only_fixed_tokens(token, value):
    assert module.login_report('JAMES_LOGIN_REPORT=' + token) == value


def test_login_report_only_from_completed_main_turn_and_never_raw_text(tmp_path):
    client, _ = fake_client([
        NS(type='agent.session.turn.output_text.done', turn_id='child', text='JAMES_LOGIN_REPORT=SIGNED_IN'),
        NS(type='agent.session.turn.output_text.done', turn_id='main', text='private-password private-account'),
        NS(type='agent.session.turn.output_text.done', turn_id='main', text='JAMES_LOGIN_REPORT=AUTH_UNAVAILABLE'),
        NS(type='agent.session.turn.completed', turn=NS(id='main', subagent_id=None)),
    ])
    path = tmp_path / 'auth-report.json'
    result = module.run_task(client, 'https://www.galaxus.ch', path, instructions='test', task='test',
        authentication_handler=lambda *args: None)
    assert result['login_report'] == 'auth_unavailable'
    assert result['model_report'] == ''
    assert 'private-password' not in path.read_text() and 'private-account' not in path.read_text()
    assert 'SIGNED_IN' not in path.read_text()


def test_conflicting_main_turn_reports_become_unknown(tmp_path):
    client, _ = fake_client([
        NS(type='agent.session.turn.output_text.done', turn_id='main', text='JAMES_LOGIN_REPORT=ACCESS_BLOCKED'),
        NS(type='agent.session.turn.output_text.done', turn_id='main', text='JAMES_LOGIN_REPORT=SIGNED_IN'),
        NS(type='agent.session.turn.completed', turn=NS(id='main', subagent_id=None)),
    ])
    result = module.run_task(client, 'https://www.galaxus.ch', tmp_path / 'conflict.json',
        instructions='test', task='test', authentication_handler=lambda *args: None)
    assert result['login_report'] == 'unknown'


def test_denied_extra_origin_is_recorded_without_retaining_its_value(tmp_path):
    client, sessions = fake_client([
        NS(type='agent.session.requires_action'),
        NS(type='agent.session.turn.completed', turn=NS(id='main', subagent_id=None)),
    ])
    sessions.retrieve.return_value = NS(required_actions=[NS(type='computer_use_approval_request',
        request_id='request-origin', request=NS(type='browser_origin_access', origin='https://private-origin.example'))])
    path = tmp_path / 'origin.json'
    result = module.run_task(client, 'https://www.galaxus.ch', path,
        instructions='test', task='test', authentication_handler=lambda *args: None)
    assert result['origin_access_denied'] is True
    assert 'private-origin.example' not in path.read_text()
    decisions = [c.kwargs['events'][0].get('response', {}) for c in sessions.events.create.call_args_list]
    assert {'type': 'browser_origin_access', 'decision': 'deny'} in decisions


def test_only_explicit_additional_login_origin_is_approved(tmp_path):
    client, sessions = fake_client([
        NS(type='agent.session.requires_action'),
        NS(type='agent.session.turn.completed', turn=NS(id='main', subagent_id=None)),
    ])
    sessions.retrieve.return_value = NS(required_actions=[
        NS(type='computer_use_approval_request', request_id='identity',
            request=NS(type='browser_origin_access', origin='https://id.digitecgalaxus.ch')),
        NS(type='computer_use_approval_request', request_id='lookalike',
            request=NS(type='browser_origin_access', origin='https://id.digitecgalaxus.ch.evil.example')),
    ])
    module.run_task(client, 'https://www.galaxus.ch/auth/v1/login', tmp_path / 'login.json',
        instructions='test', task='test', authentication_handler=lambda *args: None,
        additional_allowed_origins=('https://id.digitecgalaxus.ch',))
    responses = {event['request_id']: event['response']['decision']
        for call in sessions.events.create.call_args_list for event in call.kwargs['events'] if 'response' in event}
    assert responses == {'identity': 'approve', 'lookalike': 'deny'}


@pytest.mark.parametrize('origin', ['https://id.digitecgalaxus.ch/path', 'http://id.digitecgalaxus.ch', 'https://user:secret@id.digitecgalaxus.ch'])
def test_invalid_additional_origin_never_creates_session(tmp_path, origin):
    client, sessions = fake_client([])
    with pytest.raises(ValueError):
        module.run_task(client, 'https://www.galaxus.ch', tmp_path / 'invalid.json',
            instructions='test', task='test', additional_allowed_origins=(origin,))
    sessions.create.assert_not_called()
