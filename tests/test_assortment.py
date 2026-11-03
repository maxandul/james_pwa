from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from werkzeug.datastructures import MultiDict

from james.assortment import entries, save_entry, save_offer, save_product, source_ids
from james.extensions import db
from james.models import Activity, Category, HouseholdItem, ItemSource, Product, ProductBarcode, PurchaseSource, ShopOffer, ShoppingNeed
from james.services import Conflict, change_item
from test_app import action, csrf, login, seed_item


def source(app, home, name):
    with app.app_context():
        return db.session.scalar(select(PurchaseSource.id).where(PurchaseSource.household_id == home, PurchaseSource.name == name))


def variant(app, home, item_id, name='Coop-Milch', code=''):
    with app.app_context():
        product = save_product(home, item_id, {'product_name': name, 'package_text': '1 Liter', 'code': code})
        db.session.commit()
        return product.id


def offer(app, home, item_id, product_id, source_id, **data):
    with app.app_context():
        result = save_offer(home, item_id, product_id, {'source_id': str(source_id), 'units_per_pack': '1', **data})
        db.session.commit()
        return result.id


def test_catalogue_has_real_choices_and_manages_household_names(app, client):
    item_id, home, _ = seed_item(app)
    login(client)
    html = client.get(f'/items/{item_id}/edit').text
    assert '<select name="category"' in html and 'Migros' in html and 'Tierbedarf' in html
    response = client.post('/catalogue', data={'csrf_token': csrf(client, '/catalogue'), 'kind': 'category', 'name': 'Tiefkühlkost'})
    assert response.status_code == 302
    assert 'Tiefkühlkost' in client.get('/items/new').text
    response = client.post('/catalogue', data={'csrf_token': csrf(client, '/catalogue'), 'kind': 'category', 'name': 'TIEFKÜHLKOST'})
    assert response.status_code == 409
    with app.app_context():
        assert len([entry for entry in entries(home, 'category') if entry.name_key == 'tiefkühlkost']) == 1


def test_rename_updates_references_and_rejects_stale_forms(app, client):
    item_id, home, _ = seed_item(app)
    with app.app_context():
        entry = db.session.scalar(select(PurchaseSource).where(PurchaseSource.household_id == home, PurchaseSource.name == 'Laden'))
        save_entry(home, 'source', 'Wochenmarkt', entry.id, 1)
        db.session.commit()
        item = db.session.get(HouseholdItem, item_id)
        assert item.source == 'Wochenmarkt' and item.version == 2
        with pytest.raises(Conflict):
            save_entry(home, 'source', 'Anders', entry.id, 1)
        db.session.rollback()
    login(client)
    assert action(client, item_id, 'replenish', 1).status_code == 409


def test_undo_maps_old_category_aliases_without_recreating_names(app):
    item_id, home, user = seed_item(app)
    with app.app_context():
        event = change_item(home, user, item_id, 'edit', str(uuid4()), 1,
            data={'name': 'Kaffee', 'category': 'Pflege', 'source': 'Laden', 'unit': 'Packung', 'quantity': '2', 'stock_status': 'unknown'})
        db.session.commit()
        category = db.session.scalar(select(Category).where(Category.household_id == home, Category.name == 'Sonstiges'))
        save_entry(home, 'category', 'Speisekammer', category.id, 1)
        db.session.commit()
        change_item(home, user, item_id, 'undo', str(uuid4()), 2, activity_id=event.id)
        db.session.commit()
        assert db.session.get(HouseholdItem, item_id).category == 'Speisekammer'
        assert not db.session.scalar(select(Category.id).where(Category.household_id == home, Category.name == 'Sonstiges'))


def test_multisource_edit_undo_and_shop_filters_keep_one_need(app, client):
    item_id, home, _ = seed_item(app)
    migros = source(app, home, 'Migros')
    login(client)
    response = client.post(f'/items/{item_id}/edit', data=MultiDict([
        ('csrf_token', csrf(client, f'/items/{item_id}/edit')), ('request_id', str(uuid4())), ('version', '1'),
        ('name', 'Milch'), ('category', 'Frisches'), ('source', 'Coop'), ('quantity', '2'), ('unit', 'Packung'),
        ('stock_status', 'unknown'), ('sources_present', '1'), ('source_ids', str(migros)),
    ]))
    assert response.status_code == 302
    action(client, item_id, 'replenish', 2)
    for shop in ['Coop', 'Migros']:
        assert 'Milch' in client.get('/shopping?source='+shop).text
    with app.app_context():
        assert db.session.scalar(select(func.count(ShoppingNeed.id)).where(ShoppingNeed.item_id == item_id)) == 1
        assert db.session.scalar(select(ShoppingNeed.quantity).where(ShoppingNeed.item_id == item_id)) == 2
        item = db.session.get(HouseholdItem, item_id)
        assert len(source_ids(item)) == 2


def test_product_with_barcode_preserves_stock_and_need(app, client):
    item_id, home, _ = seed_item(app)
    product_id = variant(app, home, item_id, code='4006381333931')
    login(client)
    page = client.get(f'/items/{item_id}/products')
    assert page.status_code == 200 and 'Coop-Milch' in page.text
    with app.app_context():
        assert db.session.scalar(select(ProductBarcode.product_id)) == product_id
        assert db.session.scalar(select(ShoppingNeed.quantity).where(ShoppingNeed.item_id == item_id)) == 0
        assert db.session.get(HouseholdItem, item_id).stock_status == 'unknown'


def test_one_product_can_be_linked_to_two_shops(app):
    item_id, home, _ = seed_item(app)
    product_id = variant(app, home, item_id)
    offer(app, home, item_id, product_id, source(app, home, 'Coop'))
    offer(app, home, item_id, product_id, source(app, home, 'Migros'))
    with app.app_context():
        assert db.session.scalar(select(func.count(Product.id))) == 1
        assert db.session.scalar(select(func.count(ShopOffer.id))) == 2


def test_preferred_product_and_pack_rounding_are_shop_specific(app, client):
    item_id, home, _ = seed_item(app)
    first, second = variant(app, home, item_id, 'Variante A'), variant(app, home, item_id, 'Variante B')
    coop, migros = source(app, home, 'Coop'), source(app, home, 'Migros')
    offer(app, home, item_id, first, coop, preferred='1')
    offer(app, home, item_id, first, migros, preferred='1')
    offer(app, home, item_id, second, coop, preferred='1', units_per_pack='2', url='https://example.test/product')
    with app.app_context():
        db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == item_id)).quantity = 3
        db.session.commit()
        assert not db.session.scalar(select(ShopOffer).where(ShopOffer.product_id == first, ShopOffer.source_id == coop)).preferred
        assert db.session.scalar(select(ShopOffer).where(ShopOffer.product_id == first, ShopOffer.source_id == migros)).preferred
    login(client)
    coop_page, migros_page = client.get('/shopping?source=Coop').text, client.get('/shopping?source=Migros').text
    assert 'Variante B' in coop_page and '2 Packung(en)' in coop_page and 'mehr als benötigt' in coop_page
    assert 'Variante A' in migros_page and 'Variante B' not in migros_page


def test_multiple_unpreferred_variants_require_a_choice(app, client):
    item_id, home, _ = seed_item(app)
    for name in ['A', 'B']:
        offer(app, home, item_id, variant(app, home, item_id, name), source(app, home, 'Coop'))
    login(client)
    action(client, item_id, 'replenish', 1)
    assert 'Mehrere Produkte verfügbar' in client.get('/shopping?source=Coop').text


@pytest.mark.parametrize('quantity,url', [('0',''), ('NaN',''), ('1.0001',''), ('1','javascript:alert(1)'), ('1','https://user:secret@example.test/')], ids=['zero','nan','precision','script','credentials'])
def test_invalid_offer_is_rolled_back(app, quantity, url):
    item_id, home, _ = seed_item(app)
    product_id = variant(app, home, item_id)
    coop = source(app, home, 'Coop')
    with app.app_context():
        with pytest.raises(ValueError):
            save_offer(home, item_id, product_id, {'source_id': coop, 'units_per_pack': quantity, 'url': url})
        db.session.rollback()
        assert db.session.scalar(select(func.count(ShopOffer.id))) == 0


def test_catalogue_product_and_source_household_boundaries(app, client):
    item_id, home, _ = seed_item(app)
    foreign_item, foreign_home, _ = seed_item(app, 'other@example.test')
    product_id = variant(app, home, item_id)
    foreign_product = variant(app, foreign_home, foreign_item)
    foreign_source = source(app, foreign_home, 'Coop')
    login(client)
    assert client.get(f'/items/{item_id}/products/{foreign_product}').status_code == 404
    assert client.get(f'/items/{foreign_item}/products').status_code == 404
    result = client.post(f'/items/{item_id}/products/{product_id}/offers', data={
        'csrf_token': csrf(client, '/'), 'source_id': str(foreign_source), 'units_per_pack': '1'})
    assert result.status_code == 400
    result = client.post('/catalogue', data={'csrf_token': csrf(client, '/catalogue'), 'kind': 'source',
        'entry_id': str(foreign_source), 'version': '1', 'name': 'Verboten'})
    assert result.status_code == 404


def test_offer_replay_and_stale_product_edits_do_not_overwrite(app, client):
    item_id, home, _ = seed_item(app)
    product_id = variant(app, home, item_id)
    coop = source(app, home, 'Coop')
    offer(app, home, item_id, product_id, coop)
    with app.app_context():
        with pytest.raises(Conflict):
            save_offer(home, item_id, product_id, {'source_id': coop, 'units_per_pack': '9'})
        db.session.rollback()
        save_product(home, item_id, {'product_name': 'Neuer Name', 'version': '1'}, product_id)
        db.session.commit()
    login(client)
    result = client.post(f'/items/{item_id}/products/{product_id}', data={
        'csrf_token': csrf(client, '/'), 'product_name': 'Alter Entwurf', 'version': '1'})
    assert result.status_code == 409
    with app.app_context():
        assert db.session.get(Product, product_id).name == 'Neuer Name'
        assert db.session.scalar(select(ShopOffer.units_per_pack)) == Decimal('1')


def test_unit_change_with_active_pack_mapping_is_blocked(app):
    item_id, home, user = seed_item(app)
    product_id = variant(app, home, item_id)
    offer(app, home, item_id, product_id, source(app, home, 'Coop'))
    with app.app_context():
        with pytest.raises(Conflict, match='Produktzuordnungen'):
            change_item(home, user, item_id, 'edit', str(uuid4()), 1, data={
                'name': 'Kaffee', 'source': 'Laden', 'category': 'Vorrat', 'quantity': '2', 'unit': 'Liter', 'stock_status': 'unknown'})
        db.session.rollback()
        assert db.session.get(HouseholdItem, item_id).unit == 'Packung'


def test_undo_restores_secondary_sources(app):
    item_id, home, user = seed_item(app)
    migros = source(app, home, 'Migros')
    with app.app_context():
        event = change_item(home, user, item_id, 'edit', str(uuid4()), 1, data={
            'name': 'Milch', 'source': 'Coop', 'category': 'Frisches', 'quantity': '2',
            'unit': 'Packung', 'stock_status': 'unknown', 'sources_present': '1', 'source_ids': [str(migros)]})
        db.session.commit()
        change_item(home, user, item_id, 'undo', str(uuid4()), 2, activity_id=event.id)
        db.session.commit()
        item = db.session.get(HouseholdItem, item_id)
        assert item.source == 'Laden' and len(source_ids(item)) == 1
        assert migros not in source_ids(item)


def test_foreign_secondary_source_rolls_back_item_edit(app):
    item_id, home, user = seed_item(app)
    _, foreign_home, _ = seed_item(app, 'other@example.test')
    foreign_source = source(app, foreign_home, 'Coop')
    with app.app_context():
        with pytest.raises(ValueError, match='Haushalt'):
            change_item(home, user, item_id, 'edit', str(uuid4()), 1, data={
                'name': 'Verboten', 'source': 'Laden', 'category': 'Vorrat', 'quantity': '2',
                'unit': 'Packung', 'stock_status': 'unknown', 'sources_present': '1', 'source_ids': [str(foreign_source)]})
        db.session.rollback()
        assert db.session.get(HouseholdItem, item_id).name == 'Kaffee'
        assert db.session.get(HouseholdItem, item_id).version == 1


def test_offer_source_edit_rejects_duplicate_without_server_error(app):
    item_id, home, _ = seed_item(app)
    product_id = variant(app, home, item_id)
    coop, migros = source(app, home, 'Coop'), source(app, home, 'Migros')
    first = offer(app, home, item_id, product_id, coop)
    offer(app, home, item_id, product_id, migros)
    with app.app_context():
        with pytest.raises(Conflict):
            save_offer(home, item_id, product_id, {'source_id': migros, 'units_per_pack': '1', 'version': '1'}, first)
        db.session.rollback()
        assert db.session.get(ShopOffer, first).source_id == coop


def test_undo_unit_change_is_blocked_after_new_pack_mapping(app):
    item_id, home, user = seed_item(app)
    with app.app_context():
        event = change_item(home, user, item_id, 'edit', str(uuid4()), 1, data={
            'name': 'Milch', 'source': 'Coop', 'category': 'Frisches', 'quantity': '2',
            'unit': 'Liter', 'stock_status': 'unknown'})
        db.session.commit()
        event_id = event.id
    product_id = variant(app, home, item_id)
    offer(app, home, item_id, product_id, source(app, home, 'Coop'))
    with app.app_context():
        with pytest.raises(Conflict, match='Einheit'):
            change_item(home, user, item_id, 'undo', str(uuid4()), 2, activity_id=event_id)
        db.session.rollback()
        assert db.session.get(HouseholdItem, item_id).unit == 'Liter'


@pytest.mark.parametrize('existing', [False, True])
def test_offer_rejects_stale_unit_on_creation_and_reactivation(app, client, existing):
    item_id, home, user = seed_item(app)
    product_id = variant(app, home, item_id)
    coop = source(app, home, 'Coop')
    offer_id = offer(app, home, item_id, product_id, coop, active='0') if existing else None
    login(client)
    assert 'name="item_unit" value="Packung"' in client.get(f'/items/{item_id}/products').text
    with app.app_context():
        change_item(home, user, item_id, 'edit', str(uuid4()), 1, data={
            'name': 'Milch', 'source': 'Laden', 'category': 'Vorrat',
            'quantity': '2', 'unit': 'Liter', 'stock_status': 'unknown'})
        db.session.commit()
    path = f'/items/{item_id}/products/{product_id}/offers' + (f'/{offer_id}' if existing else '')
    data = {'csrf_token': csrf(client, '/'), 'source_id': str(coop),
            'units_per_pack': '6', 'item_unit': 'Packung', 'active': '1', 'version': '1'}
    assert client.post(path, data=data).status_code == 409
    with app.app_context():
        if existing:
            assert not db.session.get(ShopOffer, offer_id).active
        else:
            assert db.session.scalar(select(func.count(ShopOffer.id))) == 0
    # Missing units cannot bypass the check, and a freshly reviewed conversion succeeds.
    data.pop('item_unit')
    assert client.post(path, data=data).status_code == 409
    data['item_unit'] = 'Liter'
    assert client.post(path, data=data).status_code == 302
