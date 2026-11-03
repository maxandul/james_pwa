import re
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from sqlalchemy import event, select

from james.assortment import save_offer, save_product, shopping_options
from james.browsing import PAGE_SIZE
from james.extensions import db
from james.models import HouseholdItem, ItemSource, PurchaseSource, ShoppingNeed
from test_app import csrf, login, seed_item


def catalogue(app, count=115):
    first, home, user = seed_item(app)
    with app.app_context():
        # Duplicate names deliberately exercise the stable ID tie-breaker.
        items = [HouseholdItem(household_id=home, name=f'Artikel {i // 2:04d}',
            category='Vorrat' if i % 2 else 'Frisches', source='Laden', stock_status='low' if i % 2 else 'available',
            is_favorite=i < 4) for i in range(count - 1)]
        db.session.add_all(items)
        db.session.flush()
        db.session.add_all([ShoppingNeed(item_id=item.id, quantity=2 if i < 5 else 0) for i, item in enumerate(items)])
        db.session.commit()
    return first, home, user


def row_ids(html):
    return re.findall(r'data-item-id="(\d+)"', html)


def test_pages_are_bounded_stably_ordered_and_cover_all_articles(app, client):
    catalogue(app)
    login(client)
    pages = [client.get(f'/?page={page}').text for page in (1, 2, 3)]
    ids = [row_ids(html) for html in pages]
    assert list(map(len, ids)) == [PAGE_SIZE, PAGE_SIZE, 115 - 2 * PAGE_SIZE]
    assert len(set(sum(ids, []))) == 115
    assert row_ids(client.get('/?page=2').text) == ids[1]
    assert '49–96 von 115 Artikeln' in pages[1]
    assert 'Seite 2 von 3' in pages[1]
    for value in ('0', '-10', 'invalid'):
        assert row_ids(client.get(f'/?page={value}').text) == ids[0]
    response = client.get('/?page=99999999999999')
    assert response.status_code == 302
    assert parse_qs(urlsplit(response.location).query)['page'] == ['3']
    assert row_ids(client.get(response.location).text) == ids[2]


def test_search_and_combined_filters_run_before_pagination(app, client):
    catalogue(app, 140)
    login(client)
    html = client.get('/?q=Artikel&filter_category=Vorrat&filter_stock=low&filter_source=Laden').text
    assert '1–48 von 69 Artikeln' in html
    assert len(row_ids(html)) == PAGE_SIZE
    assert 'filter_category=Vorrat' in html and 'filter_stock=low' in html
    second = client.get('/?q=Artikel&filter_category=Vorrat&filter_stock=low&filter_source=Laden&page=2').text
    assert len(row_ids(second)) == 21
    assert not set(row_ids(html)) & set(row_ids(second))
    empty = client.get('/?filter_category=Vorrat&filter_stock=available').text
    assert not row_ids(empty)
    assert 'Kein passender Artikel.' in empty and 'Filter zurücksetzen' in empty


def test_unicode_search_and_sql_wildcards_keep_literal_substring_meaning(app, client):
    item_id, _, _ = seed_item(app)
    with app.app_context():
        item = db.session.get(HouseholdItem, item_id)
        item.name = 'Äpfel Straße 100% Bio_Qualität'
        db.session.commit()
    login(client)
    for term in ['ÄPFEL', 'strasse', '100%', 'Bio_']:
        assert row_ids(client.get('/', query_string={'q': term}).text) == [str(item_id)]
    assert not row_ids(client.get('/?q=BioX').text)
    assert not row_ids(client.get('/?q=%25x').text)


def test_source_filter_includes_links_and_active_offers_but_not_other_households(app, client):
    item_id, home, _ = seed_item(app)
    foreign_id, foreign_home, _ = seed_item(app, 'other@example.test')
    with app.app_context():
        source = db.session.scalar(select(PurchaseSource).where(PurchaseSource.household_id == home, PurchaseSource.name == 'Coop'))
        db.session.add(ItemSource(item_id=item_id, source_id=source.id))
        migros = db.session.scalar(select(PurchaseSource).where(PurchaseSource.household_id == home, PurchaseSource.name == 'Migros'))
        product = save_product(home, item_id, {'product_name': 'Alternative'})
        db.session.flush()
        save_offer(home, item_id, product.id, {'source_id': migros.id, 'units_per_pack': '1'})
        # Remove the maintained link to check the active-offer fallback explicitly.
        db.session.query(ItemSource).filter_by(item_id=item_id, source_id=migros.id).delete()
        foreign = db.session.get(HouseholdItem, foreign_id)
        foreign.name = 'Privater Artikel'
        foreign.category = 'Private Warengruppe'
        foreign.source = 'Privater Ort'
        db.session.commit()
    login(client)
    for name in ('Laden', 'Coop', 'Migros'):
        assert row_ids(client.get('/', query_string={'filter_source': name}).text) == [str(item_id)]
    html = client.get('/').text
    assert 'Privater Artikel' not in html and 'Private Warengruppe' not in html and 'Privater Ort' not in html
    assert not row_ids(client.get('/?filter_source=Privater+Ort').text)
    assert not row_ids(client.get('/?filter_category=Private+Warengruppe').text)


def test_archives_and_favorites_have_correct_totals_and_facets(app, client):
    first, home, _ = catalogue(app)
    with app.app_context():
        item = db.session.get(HouseholdItem, first)
        item.archived = True
        item.category = 'Archivgruppe'
        db.session.commit()
    login(client)
    active = client.get('/').text
    assert 'von 114 Artikeln' in active and 'Archivgruppe' not in active
    archived = client.get('/?view=archived').text
    assert row_ids(archived) == [str(first)] and 'Archivgruppe' in archived
    favorites = client.get('/?view=favorites').text
    assert len(row_ids(favorites)) == 4 and 'von 4 Artikeln' in favorites


def test_action_and_undo_keep_page_filters_and_clamp_a_vanishing_last_page(app, client):
    catalogue(app, 49)
    login(client)
    html = client.get('/?page=2&filter_source=Laden').text
    item_id = int(row_ids(html)[0])
    payload = {'csrf_token': csrf(client, '/'), 'request_id': str(uuid4()), 'version': 1,
        'action': 'archive', 'page': 2, 'filter_source': 'Laden'}
    response = client.post(f'/items/{item_id}/action', data=payload, follow_redirects=True)
    assert response.status_code == 200 and len(row_ids(response.text)) == 48
    assert 'Seite 2' not in response.text
    undo = re.search(r'(/activity/\d+/undo)', response.text).group(1)
    assert parse_qs(urlsplit(response.request.url).query)['filter_source'] == ['Laden']
    restored = client.post(undo, data={'csrf_token': csrf(client, '/'),
        'request_id': str(uuid4()), 'version': 2, 'filter_source': 'Laden'}, follow_redirects=True)
    assert 'von 49 Artikeln' in restored.text


def test_only_one_page_of_article_objects_is_hydrated(app, client):
    catalogue(app, 220)
    login(client)
    loaded = []
    def record(item, context):
        loaded.append(item.id)
    event.listen(HouseholdItem, 'load', record)
    try:
        response = client.get('/?page=3')
    finally:
        event.remove(HouseholdItem, 'load', record)
    assert response.status_code == 200
    assert len(loaded) == PAGE_SIZE


def test_shopping_source_and_offer_queries_are_constant_in_number(app):
    first, home, _ = catalogue(app, 100)
    with app.app_context():
        rows = db.session.execute(select(HouseholdItem, ShoppingNeed).join(ShoppingNeed).where(
            HouseholdItem.household_id == home)).all()
        engine = db.engine
        statements = []
        def record(conn, cursor, statement, parameters, context, many):
            statements.append(statement)
        event.listen(engine, 'before_cursor_execute', record)
        try:
            shopping_options(rows[:3])
            small = len(statements)
            statements.clear()
            shopping_options(rows)
            large = len(statements)
        finally:
            event.remove(engine, 'before_cursor_execute', record)
        assert small == large == 3


def test_edit_keeps_browse_context_without_shadowing_item_fields(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    context = {'filter_source': 'Laden', 'filter_category': 'Vorrat', 'filter_stock': 'unknown', 'page': 2}
    html = client.get(f'/items/{item_id}/edit', query_string=context).text
    assert 'name="filter_source" value="Laden"' in html and 'name="page" value="2"' in html
    response = client.post(f'/items/{item_id}/edit', data={**context,
        'csrf_token': csrf(client, '/'), 'request_id': str(uuid4()), 'version': 1,
        'name': 'Kaffee', 'quantity': 2, 'unit': 'Packung', 'source': 'Coop',
        'category': 'Frisches', 'stock_status': 'available'})
    assert response.status_code == 302
    params = parse_qs(urlsplit(response.location).query)
    for key, value in context.items():
        assert params[key] == [str(value)]
    with app.app_context():
        item = db.session.get(HouseholdItem, item_id)
        assert (item.source, item.category, item.stock_status) == ('Coop', 'Frisches', 'available')
