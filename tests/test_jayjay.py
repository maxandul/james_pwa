import re
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from werkzeug.exceptions import Forbidden, NotFound

from james.extensions import db
from james.jayjay import execute_tool, run_turn, start_turn
from james.models import Activity, ChatTurn, HouseholdItem, User
from test_app import csrf, login, seed_item


def enable(app):
    app.config.update(JAYJAY_ENABLED=True, OPENAI_API_KEY='test-only-not-a-real-key', OPENAI_MODEL='test-model')


def change_args(item_id, version=1, action='replenish', quantity=None):
    return dict(item_id=item_id, expected_version=version, action=action, quantity=quantity,
        stock_status=None, favorite=None)


def new_turn(app, user, home, prompt='Kaffee nachkaufen', request_id=None):
    with app.app_context():
        turn, created = start_turn(user, home, prompt, request_id or str(uuid4()))
        return turn.id, created


def test_unconfigured_chat_never_calls_provider(app, client, monkeypatch):
    seed_item(app)
    login(client)
    monkeypatch.setattr('james.jayjay.responses_request', lambda *a: pytest.fail('No provider call allowed'))
    assert 'Verbindung wird noch eingerichtet' in client.get('/jayjay').text
    result = client.post('/jayjay', data={'csrf_token': csrf(client, '/jayjay'), 'request_id': str(uuid4()), 'message': 'Hallo'})
    assert result.status_code == 503
    with app.app_context():
        assert db.session.scalar(select(func.count(ChatTurn.id))) == 0


def test_full_chat_turn_reads_then_changes_and_replay_never_calls_again(app, client, monkeypatch):
    item_id, home, user = seed_item(app)
    enable(app)
    login(client)
    import json
    replies = iter([
        {'status': 'completed', 'output': [{'type': 'function_call', 'call_id': 'read', 'name': 'list_items', 'arguments': json.dumps({'query':'Kaffee','view':'active'})}]},
        {'status': 'completed', 'output': [{'type': 'function_call', 'call_id': 'write', 'name': 'change_item', 'arguments': json.dumps(change_args(item_id))}]},
        {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type':'output_text','text':'Sehr wohl. Kaffee ist vorgemerkt.'}]}]},
    ])
    calls = []
    def respond(messages, deadline):
        calls.append(len(messages))
        return next(replies)
    monkeypatch.setattr('james.jayjay.responses_request', respond)
    data = {'csrf_token':csrf(client, '/jayjay'), 'request_id':str(uuid4()), 'message':'Kaffee nachkaufen'}
    assert client.post('/jayjay', data=data).status_code == 302
    assert client.post('/jayjay', data=data).status_code == 302
    assert len(calls) == 3
    page = client.get('/jayjay').text
    assert 'Sehr wohl.' in page and 'Tatsaechlich gespeicherte' in page
    with app.app_context():
        assert db.session.scalar(select(func.count(Activity.id))) == 1
        assert db.session.scalar(select(ChatTurn.state)) == 'done'


def test_same_resource_duplicate_tool_calls_do_not_add_extra_twice(app):
    item_id, home, user = seed_item(app)
    turn_id, _ = new_turn(app, user, home)
    with app.app_context():
        reads = {}
        execute_tool(turn_id, user, home, 'list_items', {'query':'Kaffee','view':'active'}, reads)
        args = change_args(item_id, action='extra', quantity=2)
        first = execute_tool(turn_id, user, home, 'change_item', args, reads)
        second = execute_tool(turn_id, user, home, 'change_item', args, reads)
        assert first == second
        assert second['item']['shopping_quantity'] == 2
        assert db.session.scalar(select(func.count(Activity.id))) == 1


def test_multiple_articles_can_finish_within_four_model_rounds(app, monkeypatch):
    import json
    from james.models import ShoppingNeed
    from james.services import create_item
    coffee, home, user = seed_item(app)
    with app.app_context():
        milk = create_item(home, {'name': 'Milch', 'quantity': '1'}).id
        db.session.commit()
    turn_id, _ = new_turn(app, user, home, 'Kaffee und Milch nachkaufen')
    def call(call_id, name, args):
        return {'type': 'function_call', 'call_id': call_id, 'name': name, 'arguments': json.dumps(args)}
    replies = iter([
        {'status': 'completed', 'output': [call('read-coffee', 'list_items', {'query':'Kaffee','view':'active'}),
            call('read-milk', 'list_items', {'query':'Milch','view':'active'})]},
        {'status': 'completed', 'output': [call('write-coffee', 'change_item', change_args(coffee)),
            call('write-milk', 'change_item', change_args(milk))]},
        {'status': 'completed', 'output': [{'type':'message','content':[{'type':'output_text','text':'Beide vorgemerkt.'}]}]},
    ])
    monkeypatch.setattr('james.jayjay.responses_request', lambda *args: next(replies))
    with app.app_context():
        result = run_turn(turn_id, user, home)
        assert result.state == 'done' and len(result.actions) == 2
        assert db.session.get(ShoppingNeed, coffee).quantity == 2
        assert db.session.get(ShoppingNeed, milk).quantity == 1


def test_provider_request_uses_fast_mode_and_allows_batched_tools(app, monkeypatch):
    import io
    import json
    import time
    from james.jayjay import responses_request
    def respond(request, timeout):
        payload = json.loads(request.data)
        assert payload['reasoning'] == {'effort': 'none'}
        assert payload['parallel_tool_calls'] is True
        assert payload['store'] is False and payload['max_output_tokens'] == 1200
        assert 0 < timeout <= 20
        return io.BytesIO(b'{"status":"completed","output":[]}')
    monkeypatch.setattr('james.jayjay.urlopen', respond)
    enable(app)
    with app.app_context():
        responses_request([{'role':'user','content':'Hallo'}], time.monotonic() + 20)


def test_model_failure_preserves_recorded_writes_and_marks_turn_failed(app, monkeypatch):
    item_id, home, user = seed_item(app)
    turn_id, _ = new_turn(app, user, home)
    with app.app_context():
        reads = {}
        execute_tool(turn_id, user, home, 'list_items', {'query':'Kaffee','view':'active'}, reads)
        execute_tool(turn_id, user, home, 'change_item', change_args(item_id), reads)
        def unavailable(*args):
            raise ValueError('network failure')
        monkeypatch.setattr('james.jayjay.responses_request', unavailable)
        result = run_turn(turn_id, user, home)
        assert result.state == 'failed' and len(result.actions) == 1
        assert db.session.scalar(select(func.count(Activity.id))) == 1


def test_tools_cannot_change_unread_or_foreign_items(app):
    item_id, home, user = seed_item(app)
    other_id, other_home, other_user = seed_item(app, 'other@example.test')
    turn_id, _ = new_turn(app, user, home)
    with app.app_context():
        with pytest.raises(ValueError):
            execute_tool(turn_id, user, home, 'change_item', change_args(item_id), {})
        db.session.rollback()
        reads = {}
        result = execute_tool(turn_id, user, home, 'list_items', {'query':'','view':'active'}, reads)
        assert {entry['id'] for entry in result['items']} == {item_id}
        with pytest.raises(ValueError):
            execute_tool(turn_id, user, home, 'change_item', change_args(other_id), reads)
        db.session.rollback()
        with pytest.raises(Forbidden):
            execute_tool(turn_id, other_user, other_home, 'list_items', {'query':'','view':'active'}, {})


def test_revoked_auth_version_stops_delayed_tools(app):
    item_id, home, user = seed_item(app)
    turn_id, _ = new_turn(app, user, home)
    with app.app_context():
        db.session.get(User, user).auth_version += 1
        db.session.commit()
        with pytest.raises(Forbidden):
            execute_tool(turn_id, user, home, 'list_items', {'query':'','view':'active'}, {})


def test_new_items_require_search_and_duplicate_create_is_idempotent(app):
    _, home, user = seed_item(app)
    turn_id, _ = new_turn(app, user, home)
    args = {'name':'Milch','unit':'Packung','default_quantity':1}
    with app.app_context():
        reads = {}
        with pytest.raises(ValueError):
            execute_tool(turn_id, user, home, 'create_item', args, reads)
        db.session.rollback()
        execute_tool(turn_id, user, home, 'list_items', {'query':'Milch','view':'active'}, reads)
        first = execute_tool(turn_id, user, home, 'create_item', args, reads)
        second = execute_tool(turn_id, user, home, 'create_item', args, reads)
        assert first == second
        execute_tool(turn_id, user, home, 'change_item', change_args(first['item']['id']), reads)
        assert db.session.scalar(select(func.count(HouseholdItem.id))) == 2


def test_unknown_tool_and_extra_fields_are_rejected(app):
    _, home, user = seed_item(app)
    turn_id, _ = new_turn(app, user, home)
    with app.app_context():
        for name, args in [('execute_sql', {'sql':'DROP TABLE user'}),
            ('list_items', {'query':'','view':'active','household_id':99})]:
            with pytest.raises(ValueError):
                execute_tool(turn_id, user, home, name, args, {})


def test_whitespace_cannot_bypass_existing_article_detection(app):
    _, home, user = seed_item(app)
    turn_id, _ = new_turn(app, user, home)
    with app.app_context():
        reads = {}
        execute_tool(turn_id, user, home, 'list_items', {'query':'Kaffee','view':'active'}, reads)
        with pytest.raises(ValueError, match='bereits vorhanden'):
            execute_tool(turn_id, user, home, 'create_item',
                {'name':' Kaffee ', 'unit':'Packung', 'default_quantity':1}, reads)
        db.session.rollback()
        assert db.session.scalar(select(func.count(HouseholdItem.id))) == 1


def test_chat_is_private_and_escapes_user_and_model_text(app, client, monkeypatch):
    _, home, user = seed_item(app)
    enable(app)
    monkeypatch.setattr('james.jayjay.responses_request', lambda *args: {'status':'completed',
        'output':[{'type':'message','content':[{'type':'output_text','text':'<script>alert(1)</script>'}]}]})
    login(client)
    client.post('/jayjay', data={'csrf_token':csrf(client, '/jayjay'), 'request_id':str(uuid4()),'message':'<b>Private Nachricht</b>'})
    html = client.get('/jayjay').text
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
    assert '<b>Private Nachricht</b>' not in html
    client.post('/logout', data={'csrf_token':csrf(client, '/')})
    login(client, 'member@example.test')
    assert 'Private Nachricht' not in client.get('/jayjay').text


def test_chat_request_lease_and_payload_reuse_are_checked(app):
    _, home, user = seed_item(app)
    request_id = str(uuid4())
    with app.app_context():
        first, created = start_turn(user, home, 'Hallo\nJayJay', request_id)
        again, created_again = start_turn(user, home, 'Hallo\nJayJay', request_id)
        assert created and not created_again and first.id == again.id
        with pytest.raises(ValueError):
            start_turn(user, home, 'Anderer Text', request_id)
        db.session.rollback()
        with pytest.raises(ValueError):
            start_turn(user, home, 'Noch ein Auftrag', str(uuid4()))


def test_run_scope_checked_before_provider_is_called(app, monkeypatch):
    _, home, user = seed_item(app)
    _, foreign_home, foreign_user = seed_item(app, 'other@example.test')
    turn_id, _ = new_turn(app, user, home)
    monkeypatch.setattr('james.jayjay.responses_request', lambda *args: pytest.fail('Cannot read foreign turn'))
    with app.app_context(), pytest.raises(NotFound):
        run_turn(turn_id, foreign_user, foreign_home)


def test_incomplete_model_response_never_executes_its_tools(app, monkeypatch):
    _, home, user = seed_item(app)
    turn_id, _ = new_turn(app, user, home)
    monkeypatch.setattr('james.jayjay.responses_request', lambda *args: {'status':'incomplete',
        'output':[{'type':'function_call','call_id':'partial','name':'list_items','arguments':'{}'}]})
    monkeypatch.setattr('james.jayjay.execute_tool', lambda *args: pytest.fail('No partial response tools'))
    with app.app_context():
        turn = run_turn(turn_id, user, home)
        assert turn.state == 'failed' and turn.actions == []


def test_floating_chat_is_available_on_app_pages_without_a_navigation_tab(app, client):
    seed_item(app)
    assert 'id="jayjay-launcher"' not in client.get('/login').text
    login(client)
    for path in ('/', '/shopping', '/household'):
        html = client.get(path, follow_redirects=True).text
        assert 'id="jayjay-launcher"' in html and 'id="jayjay-dialog"' in html
        nav = re.search(r'<nav class="nav".*?</nav>', html, re.S)[0]
        assert '/jayjay' not in nav
    panel = client.get('/jayjay?panel=1')
    assert panel.is_json and panel.headers['Cache-Control'] == 'no-store'
    assert panel.json['changed'] is False
    assert '<html' not in panel.json['html']


def test_panel_submission_returns_private_escaped_history_and_does_not_repeat_actions(app, client, monkeypatch):
    import json
    item, home, user = seed_item(app)
    enable(app)
    login(client)
    responses = iter([
        {'status':'completed','output':[{'type':'function_call','call_id':'read','name':'list_items','arguments':json.dumps({'query':'Kaffee','view':'active'})}]},
        {'status':'completed','output':[{'type':'function_call','call_id':'write','name':'change_item','arguments':json.dumps(change_args(item))}]},
        {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'<script>saved</script>'}]}]},
    ])
    monkeypatch.setattr('james.jayjay.responses_request', lambda *args: next(responses))
    data = {'csrf_token':csrf(client, '/jayjay'), 'request_id':str(uuid4()), 'message':'Kaffee nachkaufen (privater Testauftrag)'}
    result = client.post('/jayjay?panel=1', data=data)
    assert result.status_code == 200 and result.json['changed'] is True
    assert result.json['owner'].startswith(str(user) + ':')
    assert '&lt;script&gt;' in result.json['html'] and '<script>' not in result.json['html']
    assert client.post('/jayjay?panel=1', data=data).status_code == 200
    with app.app_context():
        assert db.session.scalar(select(func.count(Activity.id))) == 1
    client.post('/logout', data={'csrf_token':csrf(client, '/')})
    login(client, 'member@example.test')
    assert 'privater Testauftrag' not in client.get('/jayjay?panel=1').json['html']
