from sqlalchemy import select

from james.extensions import db
from james.models import HouseholdItem, Membership, ShoppingNeed
from test_app import action, csrf, login, seed_item


def test_public_installation_assets_and_worker_scope(client):
    response = client.get('/manifest.webmanifest')
    assert response.status_code == 200 and response.mimetype == 'application/manifest+json'
    manifest = response.json
    assert manifest['start_url'] == '/' and manifest['scope'] == '/'
    assert manifest['display'] == 'standalone'
    assert {icon['sizes'] for icon in manifest['icons']} == {'192x192', '512x512'}
    for icon in manifest['icons']:
        assert client.get(icon['src']).data.startswith(b'\x89PNG')
    worker = client.get('/sw.js')
    assert worker.status_code == 200 and worker.mimetype == 'text/javascript'
    assert worker.headers['Cache-Control'] == 'no-cache'


def test_offline_shell_contains_no_account_data_or_csrf(client):
    login(client)
    html = client.get('/offline').text
    assert 'Testhaushalt' not in html and 'owner@example.test' not in html
    assert 'csrf_token' not in html and '<form' not in html
    assert 'data-offline-page="true"' in html


def test_snapshot_requires_login_and_active_membership(app, client):
    assert client.get('/api/offline-list').status_code == 401
    assert client.get('/api/offline-list').headers['Cache-Control'] == 'no-store'
    login(client)
    with app.app_context():
        membership = db.session.scalar(select(Membership).where(Membership.user_id == 1))
        membership.active = False
        db.session.commit()
    response = client.get('/api/offline-list')
    assert response.status_code == 403 and response.json == {'error': 'membership_required'}


def test_snapshot_is_complete_household_scoped_and_read_only(app, client):
    item_id, _, _ = seed_item(app)
    other_id, _, _ = seed_item(app, 'other@example.test')
    login(client)
    action(client, item_id, 'replenish', 1)
    with app.app_context():
        other = db.session.get(HouseholdItem, other_id)
        other.name = 'Fremdes Geheimnis'
        db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == other_id)).quantity = 9
        db.session.commit()
    response = client.get('/api/offline-list?household_id=2&source=other')
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
    snapshot = response.json
    assert snapshot['household'] == 'Testhaushalt' and snapshot['owner'].startswith('1:')
    assert snapshot['saved_at'].endswith('Z')
    assert len(snapshot['items']) == 1
    assert snapshot['items'][0]['name'] == 'Kaffee' and snapshot['items'][0]['quantity'] == 2
    assert 'password' not in response.text and 'csrf' not in response.text and 'Fremdes' not in response.text
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity).where(ShoppingNeed.item_id == item_id)) == 2


def test_logout_clears_device_storage_and_pages_load_pwa(client):
    login(client)
    html = client.get('/').text
    assert 'data-offline-owner="1:' in html and 'rel="manifest"' in html
    response = client.post('/logout', data={'csrf_token': csrf(client, '/')})
    assert response.headers['Clear-Site-Data'] == '"storage", "cache"'
    assert 'data-offline-owner=""' in client.get('/login').text
