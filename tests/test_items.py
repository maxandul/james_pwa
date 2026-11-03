import re
from uuid import uuid4

import pytest
from sqlalchemy import select

from james.extensions import db
from james.models import Activity, HouseholdItem, ShoppingNeed
from test_app import action, csrf, login, seed_item


def change(client, item_id, action_name, version, **fields):
    return client.post(f"/items/{item_id}/action", data={"csrf_token": csrf(client, "/"),
        "request_id": str(uuid4()), "action": action_name, "version": version, **fields})


def edit(client, item_id, version, **fields):
    data = {"name": "Kaffee", "category": "Vorrat", "source": "Coop", "unit": "Packung",
        "quantity": "2", "stock_status": "available", **fields}
    return client.post(f"/items/{item_id}/edit", data={"csrf_token": csrf(client, "/"),
        "request_id": str(uuid4()), "version": version, **data})


def undo_response(client, response, version):
    event_id = int(re.search(r"undo=(\d+)", response.location).group(1))
    return client.post(f"/activity/{event_id}/undo", data={"csrf_token": csrf(client, "/"),
        "request_id": str(uuid4()), "version": version})


def test_edit_and_undo_restore_metadata(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    assert client.get(f"/items/{item_id}/edit").status_code == 200
    response = edit(client, item_id, 1, name="Espresso", quantity="3", favorite="1")
    assert response.status_code == 302
    with app.app_context():
        item = db.session.get(HouseholdItem, item_id)
        assert (item.name, item.default_quantity, item.source, item.is_favorite, item.stock_status) == ("Espresso", 3, "Coop", True, "available")
    assert undo_response(client, response, 2).status_code == 302
    with app.app_context():
        item = db.session.get(HouseholdItem, item_id)
        assert (item.name, item.default_quantity, item.source, item.is_favorite, item.stock_status) == ("Kaffee", 2, "Laden", False, "unknown")


@pytest.mark.parametrize("status", ["available", "low", "empty", "unknown"])
def test_stock_correction_never_changes_shopping_need(app, client, status):
    item_id, _, _ = seed_item(app)
    login(client)
    action(client, item_id, "replenish", 1)
    result = change(client, item_id, "status", 2, stock_status=status)
    assert result.status_code == 302
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2
        assert db.session.get(HouseholdItem, item_id).stock_status == status
    assert undo_response(client, result, 3).status_code == 302
    with app.app_context():
        assert db.session.get(HouseholdItem, item_id).stock_status == "low"


def test_remove_need_does_not_mark_as_purchased_and_can_be_undone(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    action(client, item_id, "empty", 1)
    response = change(client, item_id, "remove", 2)
    assert response.status_code == 302
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 0
        assert db.session.get(HouseholdItem, item_id).stock_status == "empty"
    assert undo_response(client, response, 3).status_code == 302
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2


def test_favorites_are_shared_filtered_and_retries_are_idempotent(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    data = {"csrf_token": csrf(client, "/"), "request_id": str(uuid4()), "version": 1, "action": "favorite", "favorite": "1"}
    assert client.post(f"/items/{item_id}/action", data=data).status_code == 302
    assert client.post(f"/items/{item_id}/action", data=data).status_code == 302
    assert f'/items/{item_id}/edit' in client.get("/?view=favorites").text
    second = app.test_client()
    login(second, "member@example.test")
    assert 'aria-pressed="true"' in second.get("/?view=favorites").text
    assert change(client, item_id, "favorite", 2, favorite="0").status_code == 302
    assert f'/items/{item_id}/edit' not in client.get("/?view=favorites").text
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 0


def test_archive_requires_empty_list_and_preserves_item(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    action(client, item_id, "replenish", 1)
    assert change(client, item_id, "archive", 2).status_code == 409
    assert change(client, item_id, "remove", 2).status_code == 302
    result = change(client, item_id, "archive", 3)
    assert result.status_code == 302
    assert f'/items/{item_id}/edit' not in client.get("/").text
    archive = client.get("/?view=archived").text
    assert "Kaffee" in archive and "Wieder aktivieren" in archive
    assert undo_response(client, result, 4).status_code == 302
    assert f'/items/{item_id}/edit' in client.get("/").text


def test_archived_items_cannot_be_reordered_and_can_be_restored(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    assert change(client, item_id, "archive", 1).status_code == 302
    for action_name in ("replenish", "empty", "favorite", "status", "extra", "purchase"):
        assert change(client, item_id, action_name, 2, favorite="1", stock_status="available", quantity="1").status_code == 409
    assert edit(client, item_id, 2).status_code == 409
    assert change(client, item_id, "restore", 2).status_code == 302
    assert change(client, item_id, "replenish", 3).status_code == 302
    with app.app_context():
        assert db.session.get(HouseholdItem, item_id).archived is False
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2


def test_stale_edit_is_rejected_and_requires_reload(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    change(client, item_id, "favorite", 1, favorite="1")
    response = edit(client, item_id, 1, name="Old tab")
    assert response.status_code == 409
    assert "Aktuellen Artikel neu laden" in response.text
    assert "Änderungen speichern" not in response.text
    with app.app_context():
        assert db.session.get(HouseholdItem, item_id).name == "Kaffee"


def test_unit_change_cannot_reinterpret_pending_quantity(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    action(client, item_id, "replenish", 1)
    assert edit(client, item_id, 2, unit="Flasche").status_code == 409
    with app.app_context():
        assert db.session.get(HouseholdItem, item_id).unit == "Packung"
    change(client, item_id, "remove", 2)
    assert edit(client, item_id, 3, unit="Flasche").status_code == 302


def test_item_management_respects_household_boundaries(app, client):
    item_id, _, _ = seed_item(app, "other@example.test")
    login(client)
    assert client.get(f"/items/{item_id}/edit").status_code == 404
    assert edit(client, item_id, 1).status_code == 404
    for action_name in ("favorite", "status", "remove", "archive", "restore"):
        assert change(client, item_id, action_name, 1, favorite="1", stock_status="available").status_code == 404


def test_invalid_status_and_edit_leave_existing_data_intact(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    assert change(client, item_id, "status", 1, stock_status="made-up").status_code == 400
    assert edit(client, item_id, 1, name="", favorite="1").status_code == 400
    with app.app_context():
        item = db.session.get(HouseholdItem, item_id)
        assert item.name == "Kaffee" and item.stock_status == "unknown" and not item.is_favorite


def test_search_and_edit_forms_offer_labelled_controls(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    assert f'/items/{item_id}/edit' in client.get("/?q=KAFF").text
    assert f'/items/{item_id}/edit' not in client.get("/?q=Milch").text
    html = client.get(f"/items/{item_id}/edit").text
    assert 'inputmode="numeric"' in html
    assert 'name="stock_status"' in html
    assert 'type="checkbox"' in html


def test_favorite_view_and_search_survive_card_action(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    response = change(client, item_id, "favorite", 1, favorite="1", view="favorites", q="kaff")
    assert "view=favorites" in response.location and "q=kaff" in response.location
    assert f'/items/{item_id}/edit' in client.get(response.location).text


def test_undo_accepts_legacy_stock_only_snapshot(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    response = action(client, item_id, "replenish", 1)
    with app.app_context():
        event = db.session.scalar(select(Activity))
        event.before_state = {"status": "unknown", "quantity": 0}
        db.session.commit()
    assert undo_response(client, response, 2).status_code == 302
    with app.app_context():
        item = db.session.get(HouseholdItem, item_id)
        assert item.stock_status == "unknown" and not item.archived and not item.is_favorite
