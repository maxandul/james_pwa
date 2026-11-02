import re
from uuid import uuid4

import pytest
from sqlalchemy import select

from james.extensions import db
from james.models import Activity, HouseholdItem, PurchasePlan, PurchaseSource, ShoppingNeed
from james.planning import reservations
from james.services import change_item
from test_app import action, csrf, login, seed_item
from test_assortment import offer, source, variant


def setup_plan(app, client):
    item_id, home, user = seed_item(app)
    login(client)
    action(client, item_id, 'replenish', 1)
    return item_id, home, user, source(app, home, 'Laden')


def plan_form(client, source_id, **values):
    html = client.get(f'/plans?source_id={source_id}').text
    return {'csrf_token': re.search(r'name="csrf_token" value="([^"]+)"', html)[1],
        'review_token': re.search(r'name="review_token" value="([^"]+)"', html)[1],
        'source_id': str(source_id), **values}


def make_plan(client, item_id, source_id, amount=2):
    data = plan_form(client, source_id, **{f'include_{item_id}': '1', f'quantity_{item_id}': str(amount)})
    response = client.post('/plans', data=data)
    assert response.status_code == 302, response.text
    return response.headers['Location'], data


def transition(client, path, version, action_name, **data):
    return client.post(path, data={'csrf_token': csrf(client, path), 'version': str(version), 'action': action_name, **data})


def test_preparation_reserves_once_without_purchasing_and_replay_is_safe(app, client):
    item_id, home, _, shop = setup_plan(app, client)
    path, data = make_plan(client, item_id, shop)
    assert client.post('/plans', data=data).headers['Location'] == path
    assert 'bereits eingeplant' in client.get('/shopping').text
    with app.app_context():
        assert reservations(home) == {item_id: 2}
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2
        assert db.session.get(HouseholdItem, item_id).stock_status == 'low'
        assert len(db.session.scalars(select(PurchasePlan)).all()) == 1
        assert len(db.session.scalars(select(Activity)).all()) == 1


def test_second_stale_plan_cannot_allocate_reserved_demand(app, client):
    item_id, home, _, shop = setup_plan(app, client)
    stale = plan_form(client, shop, **{f'include_{item_id}': '1', f'quantity_{item_id}': '2'})
    make_plan(client, item_id, shop)
    assert client.post('/plans', data=stale).status_code == 409
    with app.app_context():
        assert reservations(home)[item_id] == 2


def test_explicit_order_confirmation_and_close_do_not_book_goods(app, client):
    item_id, home, _, shop = setup_plan(app, client)
    path, _ = make_plan(client, item_id, shop)
    assert transition(client, path, 1, 'ordered').status_code == 400
    assert transition(client, path, 1, 'ordered', confirm_ordered='1', reference='ABC-42').status_code == 302
    assert transition(client, path, 1, 'cancelled').status_code == 409
    assert transition(client, path, 2, 'closed').status_code == 302
    with app.app_context():
        assert reservations(home) == {}
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2
        assert db.session.scalar(select(PurchasePlan.reference)) == 'ABC-42'


@pytest.mark.parametrize('purchase_action', ['purchase', 'receipt', 'remove'])
def test_completed_demand_never_reserves_future_replenishment(app, client, purchase_action):
    item_id, home, user, shop = setup_plan(app, client)
    make_plan(client, item_id, shop)
    with app.app_context():
        change_item(home, user, item_id, purchase_action, str(uuid4()), 2, quantity='2')
        db.session.commit()
        assert reservations(home).get(item_id, 0) == 0
        change_item(home, user, item_id, 'replenish', str(uuid4()), 3)
        db.session.commit()
        assert reservations(home).get(item_id, 0) == 0


def test_partial_purchase_clamps_reservations_and_undo_does_not_reactivate_them(app, client):
    item_id, home, user, shop = setup_plan(app, client)
    path, _ = make_plan(client, item_id, shop)
    with app.app_context():
        event = change_item(home, user, item_id, 'purchase', str(uuid4()), 2, quantity='1')
        db.session.commit()
        assert reservations(home)[item_id] == 1
        change_item(home, user, item_id, 'undo', str(uuid4()), 3, activity_id=event.id)
        db.session.commit()
        assert reservations(home)[item_id] == 1
    assert transition(client, path, 1, 'cancelled').status_code == 409


def test_pack_rounding_and_stale_offer_product_changes(app, client):
    item_id, home, _, shop = setup_plan(app, client)
    product_id = variant(app, home, item_id, 'Kaffee Spezial')
    offer(app, home, item_id, product_id, shop, units_per_pack='3', url='https://example.test/coffee')
    stale = plan_form(client, shop, **{f'include_{item_id}': '1', f'quantity_{item_id}': '2'})
    from james.assortment import save_product
    with app.app_context():
        save_product(home, item_id, {'product_name': 'Kaffee Neu', 'version': '1'}, product_id)
        db.session.commit()
    assert client.post('/plans', data=stale).status_code == 409
    path, _ = make_plan(client, item_id, shop)
    html = client.get(path).text
    assert 'Kaffee Neu' in html and '1 Packung(en), 3 Packung' in html
    assert 'https://example.test/coffee' in html


def test_plan_scope_and_tampered_review(app, client):
    item_id, _, _, shop = setup_plan(app, client)
    path, data = make_plan(client, item_id, shop, 1)
    data['review_token'] += 'wrong'
    assert client.post('/plans', data=data).status_code == 409
    client.post('/logout', data={'csrf_token': csrf(client, '/')})
    login(client, 'other@example.test')
    assert client.get(path).status_code == 404
    assert transition(client, path, 1, 'cancelled').status_code == 404
    assert client.post('/plans', data={**data, 'csrf_token': csrf(client, '/')}).status_code == 404


def test_multirow_plan_failure_rolls_back_all_reservations(app, client):
    item_id, home, _, shop = setup_plan(app, client)
    from james.services import create_item
    with app.app_context():
        second = create_item(home, {'name': 'Milch'})
        second_id = second.id
        db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == second_id)).quantity = 1
        db.session.commit()
    data = plan_form(client, shop, **{f'include_{item_id}': '1', f'quantity_{item_id}': '1',
        f'include_{second_id}': '1', f'quantity_{second_id}': '2'})
    assert client.post('/plans', data=data).status_code == 409
    with app.app_context():
        assert reservations(home) == {}
