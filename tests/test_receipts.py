from hashlib import sha256
from io import BytesIO
import re
import subprocess
import time
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from james.extensions import db
from james.models import Activity, HouseholdItem, ReceiptImport, ShoppingNeed
from james.receipt_text import clean_receipt_text, extract_text, parse_lines, run_tool
from james.receipts import create_draft
from james.services import change_item
from test_app import action, csrf, login, seed_item


def draft(client, text='Kaffee 4.50\nMilch 1.80'):
    response = client.post('/receipts/new', data={'csrf_token': csrf(client, '/receipts/new'), 'text': text})
    assert response.status_code == 302
    return response.headers['Location']


def form(client, path, **data):
    html = client.get(path).text
    return {'csrf_token': re.search(r'name="csrf_token" value="([^"]+)"', html)[1],
        'review_token': re.search(r'name="review_token" value="([^"]+)"', html)[1], **data}


def test_receipt_parser_does_not_book_totals_or_discounts():
    rows = parse_lines('2 x Kaffee 4.50 9.00\nMilch 1.80\nTotal CHF 10.80\nRabatt 1.00\nTWINT 10.80')
    assert [(row['label'], row['quantity']) for row in rows] == [('Kaffee', 2), ('Milch', 1)]
    with pytest.raises(ValueError):
        parse_lines('\n'.join('Milch' for _ in range(61)))
    with pytest.raises(ValueError):
        clean_receipt_text('x' * 24001)


def test_draft_never_changes_stock_and_duplicate_text_returns_same_draft(app, client):
    item_id, home, _ = seed_item(app)
    login(client)
    path = draft(client)
    assert draft(client, 'Kaffee 4.50\n\nMilch 1.80') == path
    assert f'value="{item_id}" selected' in client.get(path).text
    with app.app_context():
        assert db.session.scalar(select(func.count(ReceiptImport.id))) == 1
        assert db.session.get(HouseholdItem, item_id).stock_status == 'unknown'
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 0


def test_receipt_books_existing_and_new_items_once_and_records_actual_quantity(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    action(client, item_id, 'replenish', 1)
    path = draft(client)
    data = form(client, path, target_0=str(item_id), quantity_0='3', target_1='new', name_1='Milch', quantity_1='2')
    assert client.post(path, data=data).status_code == 302
    assert client.post(path, data=data).status_code == 302
    assert draft(client) == path
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity).where(ShoppingNeed.item_id == item_id)) == 0
        assert db.session.get(HouseholdItem, item_id).stock_status == 'available'
        assert db.session.scalar(select(func.count(Activity.id)).where(Activity.action == 'receipt')) == 2
        receipt = db.session.scalar(select(ReceiptImport))
        assert receipt.rows[0]['booking']['quantity'] == 3
        assert receipt.rows[1]['booking']['unit'] == 'Packung'
    result = client.post(path + '/undo', data={'csrf_token': csrf(client, path)})
    assert result.status_code == 302
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity).where(ShoppingNeed.item_id == item_id)) == 2
        assert db.session.scalar(select(ReceiptImport.state)) == 'reversed'
        assert db.session.scalar(select(HouseholdItem).where(HouseholdItem.name == 'Milch')) is not None
    assert client.post(path, data=data).status_code == 409


def test_receipt_repeated_rows_aggregate_one_item(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    path = draft(client, 'Kaffee 4.50\nKaffee 3.00')
    assert client.post(path, data=form(client, path, target_0=str(item_id), quantity_0='2',
        target_1=str(item_id), quantity_1='1')).status_code == 302
    with app.app_context():
        assert db.session.scalar(select(func.count(Activity.id))) == 1
        assert db.session.scalar(select(ReceiptImport)).rows[1]['booking']['quantity'] == 1


def test_failed_second_row_rolls_back_new_item_and_entire_purchase(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    path = draft(client)
    data = form(client, path, target_0='new', quantity_0='1', name_0='New Coffee', target_1=str(item_id), quantity_1='0')
    assert client.post(path, data=data).status_code == 400
    with app.app_context():
        assert db.session.scalar(select(func.count(HouseholdItem.id))) == 1
        assert db.session.scalar(select(func.count(Activity.id))) == 0
        assert db.session.scalar(select(ReceiptImport.state)) == 'draft'


def test_stale_item_version_rejects_all_rows(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    path = draft(client)
    data = form(client, path, target_0=str(item_id), quantity_0='1')
    action(client, item_id, 'replenish', 1)
    assert client.post(path, data=data).status_code == 409
    with app.app_context():
        assert db.session.scalar(select(ReceiptImport.state)) == 'draft'
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2


def test_receipt_scope_and_signed_review_cannot_be_swapped(app, client):
    item_id, _, _ = seed_item(app)
    foreign_id, _, _ = seed_item(app, 'other@example.test')
    login(client)
    path = draft(client)
    data = form(client, path, target_0=str(foreign_id), quantity_0='1')
    assert client.post(path, data=data).status_code == 409
    second = draft(client, 'Kaffee 9.00')
    data['target_0'] = str(item_id)
    assert client.post(second, data=data).status_code == 409
    client.post('/logout', data={'csrf_token': csrf(client, '/')})
    login(client, 'other@example.test')
    assert client.get(path).status_code == 404
    assert client.post(path + '/undo', data={'csrf_token': csrf(client, '/')}).status_code == 404


def test_undo_conflict_is_atomic_for_all_items(app, client):
    item_id, home, user = seed_item(app)
    login(client)
    path = draft(client)
    data = form(client, path, target_0=str(item_id), quantity_0='1', target_1='new', name_1='Milch', quantity_1='1')
    client.post(path, data=data)
    with app.app_context():
        milk = db.session.scalar(select(HouseholdItem).where(HouseholdItem.name == 'Milch'))
        change_item(home, user, milk.id, 'replenish', str(uuid4()), milk.version)
        db.session.commit()
    assert client.post(path + '/undo', data={'csrf_token': csrf(client, path)}).status_code == 409
    with app.app_context():
        assert db.session.get(HouseholdItem, item_id).stock_status == 'available'
        assert db.session.scalar(select(ReceiptImport.state)) == 'confirmed'
        assert db.session.scalar(select(func.count(Activity.id)).where(Activity.action == 'undo')) == 0


def test_receipt_text_is_escaped_and_requires_explicit_selection(app, client):
    seed_item(app)
    login(client)
    path = draft(client, '<script>alert(1)</script> 1.00')
    html = client.get(path).text
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
    assert client.post(path, data=form(client, path)).status_code == 400


def test_receipt_upload_content_and_size_are_checked(app, client, monkeypatch):
    seed_item(app)
    login(client)
    result = client.post('/receipts/new', data={'csrf_token': csrf(client, '/receipts/new'),
        'receipt': (BytesIO(b'not an image'), 'photo.jpg')})
    assert result.status_code == 400
    with pytest.raises(ValueError, match='10 MB'):
        extract_text(b'\xff\xd8\xff' + b'x' * (10 * 1024 * 1024))
    monkeypatch.setattr('james.receipt_text.subprocess.run', lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired('tesseract', 20)))
    with pytest.raises(ValueError, match='nicht gelesen'):
        run_tool(['tesseract'], time.monotonic() + 1)


def test_receipt_same_fingerprint_is_scoped_to_household(app):
    _, first, _ = seed_item(app)
    _, other, _ = seed_item(app, 'other@example.test')
    with app.app_context():
        digest = sha256(b'photo').hexdigest()
        a = create_draft(first, 'Milch 1.80', digest)
        b = create_draft(other, 'Milch 1.80', digest)
        db.session.commit()
        assert a.id != b.id
