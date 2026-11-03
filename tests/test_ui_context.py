import re
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from test_app import csrf, login, seed_item


def test_shopping_source_survives_action_and_undo(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    response = client.post(f'/items/{item_id}/action', data={
        'csrf_token': csrf(client, '/'), 'request_id': str(uuid4()), 'version': 1,
        'action': 'replenish', 'return_to': 'shopping', 'source': 'Laden'})
    assert parse_qs(urlsplit(response.location).query)['source'] == ['Laden']
    html = client.get(response.location).text
    assert 'name="source" value="Laden"' in html
    event_id = parse_qs(urlsplit(response.location).query)['undo'][0]
    response = client.post(f'/activity/{event_id}/undo', data={
        'csrf_token': csrf(client, '/shopping'), 'request_id': str(uuid4()), 'version': 2,
        'return_to': 'shopping', 'source': 'Laden'})
    assert parse_qs(urlsplit(response.location).query)['source'] == ['Laden']


def test_edit_and_breadcrumb_keep_filtered_article_context(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    html = client.get(f'/items/{item_id}/edit?view=favorites&q=kaff&layout=cards').text
    assert 'aria-label="Brotkrumennavigation"' in html
    assert 'name="layout" value="cards"' in html
    assert 'view=favorites&amp;layout=cards&amp;q=kaff' in html
    response = client.post(f'/items/{item_id}/edit', data={
        'csrf_token': csrf(client, '/'), 'request_id': str(uuid4()), 'version': 1,
        'name': 'Kaffee', 'quantity': 2, 'unit': 'Packung', 'stock_status': 'available',
        'view': 'favorites', 'layout': 'cards', 'q': 'kaff'})
    context = parse_qs(urlsplit(response.location).query)
    assert (context['view'], context['layout'], context['q']) == (['favorites'], ['cards'], ['kaff'])


def test_layout_is_validated_and_public_css_dependencies_are_available(app, client):
    seed_item(app)
    login(client)
    assert 'data-layout="compact"' in client.get('/?layout=arbitrary').text
    assert 'data-layout="cards"' in client.get('/?layout=cards').text
    css = client.get('/static/app.css').text
    imports = re.findall(r'url\("([^\"]+)"\)', css)
    assert len(imports) == 6
    from pathlib import Path
    worker_text = Path('james/static/sw.js').read_text()
    for path in imports:
        url = '/static/' + path
        assert client.get(url).status_code == 200
        assert url in worker_text
