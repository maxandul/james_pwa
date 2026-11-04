from types import SimpleNamespace
from unittest.mock import Mock
import json
import stat

import pytest

from scripts.shop_browser_context import Browserbase, BrowserUnavailable, State, execute, locked_state

CONTEXT = '11111111-1111-4111-8111-111111111111'
SESSION = '22222222-2222-4222-8222-222222222222'
PROJECT = '33333333-3333-4333-8333-333333333333'


def provider():
    return SimpleNamespace(project=PROJECT, create_context=Mock(return_value=CONTEXT),
        create_session=Mock(return_value={'id': SESSION, 'connectUrl': 'secret-cdp'}),
        live_url=Mock(return_value='https://www.browserbase.com/view'),
        release=Mock(), session=Mock(return_value={'status': 'COMPLETED'}), delete_context=Mock())


def test_reopen_reuses_profile_and_never_saves_control_url(tmp_path):
    p = provider()
    state = State(tmp_path / 'state.json')
    execute('init', p, state)
    navigate = Mock()
    execute('open', p, state, navigate=navigate)
    with pytest.raises(BrowserUnavailable):
        execute('open', p, state, navigate=navigate)
    from scripts.shop_browser_context import close_session
    close_session(p, state, sleep=lambda _: None)
    execute('open', p, state, navigate=navigate)
    assert p.create_context.call_count == 1
    assert p.create_session.call_args_list[0].args == (CONTEXT,)
    assert p.create_session.call_args_list[1].args == (CONTEXT,)
    assert 'secret' not in state.path.read_text()
    assert stat.S_IMODE(state.path.stat().st_mode) == 0o600


def test_ambiguous_creation_is_not_repeated(tmp_path):
    p = provider()
    state = State(tmp_path / 'state.json')
    execute('init', p, state)
    p.create_session.side_effect = BrowserUnavailable('timeout')
    with pytest.raises(BrowserUnavailable):
        execute('open', p, state)
    with pytest.raises(BrowserUnavailable):
        execute('open', p, State(state.path))
    assert p.create_session.call_count == 1
    assert json.loads(state.path.read_text())['creation_pending'] == 'session'


def test_failed_cleanup_keeps_reference(tmp_path):
    p = provider()
    state = State(tmp_path / 'state.json')
    execute('init', p, state)
    p.release.side_effect = BrowserUnavailable('offline')
    with pytest.raises(BrowserUnavailable):
        execute('open', p, state, navigate=Mock(side_effect=RuntimeError('secret')))
    assert State(state.path).data['session_id'] == SESSION


def test_forget_deletes_provider_context(tmp_path):
    p = provider()
    state = State(tmp_path / 'state.json')
    execute('init', p, state)
    execute('forget', p, state)
    p.delete_context.assert_called_once_with(CONTEXT)
    assert State(state.path).data == {}


def test_reject_other_project(tmp_path):
    p = provider()
    state = State(tmp_path / 'state.json')
    state.data = {'project_id': CONTEXT, 'context_id': CONTEXT}
    with pytest.raises(BrowserUnavailable):
        execute('open', p, state)
    p.create_session.assert_not_called()


def test_lock_excludes_concurrent_operator(tmp_path):
    path = tmp_path / 'state.json'
    with locked_state(path):
        with pytest.raises(BrowserUnavailable):
            with locked_state(path):
                pass


def test_provider_disables_recording_and_sets_bounded_persistence():
    p = Browserbase('test-only', PROJECT)
    p.request = Mock(return_value={})
    p.create_session(CONTEXT)
    payload = p.request.call_args.args[2]
    assert payload['timeout'] == 720
    settings = payload['browserSettings']
    assert settings['context'] == {'id': CONTEXT, 'persist': True}
    assert settings['recordSession'] is False
    assert settings['logSession'] is False
    assert settings['solveCaptchas'] is False


@pytest.mark.parametrize('url', ['http://www.browserbase.com/view', 'https://evil.test/',
                               'https://www.browserbase.com.evil.test/view'])
def test_reject_unexpected_live_url(url):
    p = Browserbase('test-only', PROJECT)
    p.request = Mock(return_value={'debuggerFullscreenUrl': url})
    with pytest.raises(BrowserUnavailable):
        p.live_url(SESSION)


def test_bodyless_delete_does_not_advertise_empty_json(monkeypatch):
    from contextlib import nullcontext
    from urllib.error import HTTPError
    observed = []
    def open_request(req, timeout):
        observed.append(req)
        if req.method == 'DELETE' and req.data is None and req.has_header('Content-type'):
            raise HTTPError(req.full_url, 400, 'Empty JSON body', {}, None)
        return nullcontext(SimpleNamespace(read=lambda n: b''))
    monkeypatch.setattr('scripts.shop_browser_context.build_opener',
                        lambda *args: SimpleNamespace(open=open_request))
    p = Browserbase('synthetic-only', PROJECT)
    p.delete_context(CONTEXT)
    p.release(SESSION)
    deletion, release = observed
    assert deletion.method == 'DELETE' and deletion.data is None
    assert not deletion.has_header('Content-type')
    assert release.get_header('Content-type') == 'application/json'
    assert json.loads(release.data)['status'] == 'REQUEST_RELEASE'
