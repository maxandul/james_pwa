from datetime import timedelta
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest
from sqlalchemy import func, select

from james.barcodes import normalize_barcode, register_barcode
from james.catalog import CatalogUnavailable, cached_suggestion, fetch_suggestion, reserve_catalog_lookup, save_suggestion
from james.extensions import db
from james.models import CatalogGate, HouseholdItem, Membership, Product, ProductBarcode, ShoppingNeed, utcnow
from test_app import action, csrf, login, seed_item

EAN = "4006381333931"
UPC = "036000291452"


def scan_code(client, code=EAN, **fields):
    return client.post("/scan", data={"csrf_token": csrf(client, "/scan"), "code": code, **fields})


def register(client, code=EAN, **fields):
    return client.post("/barcodes", data={"csrf_token": csrf(client, "/scan"), "code": code,
        "product_name": "Testprodukt", "item_id": "new", **fields})


def test_scan_is_embedded_in_article_processes(client, app):
    item_id, _, _ = seed_item(app)
    login(client)
    home = client.get("/").text
    assert '>Scannen</a>' not in home
    assert '/scan?flow=replenish' in home
    assert '/scan?flow=create' in client.get('/items/new').text
    assert f'context_item_id={item_id}' in client.get(f'/items/{item_id}/edit').text


def test_create_scan_returns_to_article_without_buying(app, client):
    login(client)
    page = client.get('/scan?flow=create')
    assert 'Artikel per Barcode erfassen' in page.text
    assert 'href="/items/new"' in page.text
    unknown = scan_code(client, flow='create')
    assert 'name="flow" value="create"' in unknown.text
    result = register(client, flow='create')
    assert result.status_code == 302
    assert '/edit' in result.location
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 0
    known = scan_code(client, flow='create')
    assert 'bereits erfasst' in known.text
    assert 'name="action" value="replenish"' not in known.text


def test_article_scan_pins_target_and_returns_to_edit(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    fields = {'flow': 'assign', 'context_item_id': str(item_id)}
    unknown = scan_code(client, **fields)
    assert 'name="context_item_id"' in unknown.text
    assert 'id="barcode-target"' not in unknown.text
    assert 'id="new-item-fields"' not in unknown.text
    # A stale/default item_id must not accidentally create another article.
    result = register(client, item_id='new', **fields)
    assert result.status_code == 302 and result.location.endswith(f'/items/{item_id}/edit')
    with app.app_context():
        assert db.session.scalar(select(func.count(HouseholdItem.id))) == 1
        assert db.session.scalar(select(Product.item_id)) == item_id
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 0
    assert scan_code(client, **fields).location.endswith(f'/items/{item_id}/edit')


def test_article_scan_cannot_use_foreign_context(app, client):
    other_id, _, _ = seed_item(app, 'other@example.test')
    login(client)
    fields = {'flow': 'assign', 'context_item_id': str(other_id)}
    assert client.get(f'/scan?flow=assign&context_item_id={other_id}').status_code == 404
    assert scan_code(client, **fields).status_code == 404
    assert register(client, **fields).status_code == 404


def test_article_scan_does_not_remap_known_product(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    register(client)
    result = scan_code(client, flow='assign', context_item_id=str(item_id))
    assert result.status_code == 409
    assert 'nicht zugeordnet' in result.text
    assert 'name="action" value="replenish"' not in result.text
    assert register(client, flow='assign', context_item_id=str(item_id)).status_code == 409
    with app.app_context():
        assert db.session.scalar(select(Product.item_id)) != item_id


def test_scan_context_survives_catalogue_failure_and_invalid_code(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    fields = {'flow': 'assign', 'context_item_id': str(item_id)}
    invalid = scan_code(client, code='123', **fields)
    assert invalid.status_code == 400
    assert f'href="/items/{item_id}/edit"' in invalid.text
    with patch('james.scan.fetch_suggestion', side_effect=CatalogUnavailable('Manuell erfassen')):
        result = scan_code(client, lookup='1', product_name='Entwurf', **fields)
    assert result.status_code == 200
    assert 'value="Entwurf"' in result.text
    assert 'name="flow" value="assign"' in result.text
    assert f'name="context_item_id" value="{item_id}"' in result.text


@pytest.mark.parametrize("code", [EAN, UPC, "96385074", "00036000291452"])
def test_valid_gtins_preserve_original_digits(code):
    original, canonical = normalize_barcode(code)
    assert original == code and len(canonical) == 14


def test_upc_and_ean_aliases_resolve_to_same_gtin():
    assert normalize_barcode(UPC)[1] == normalize_barcode("0" + UPC)[1]
    assert normalize_barcode(" 4006 3813 33931 ")[0] == EAN


@pytest.mark.parametrize("code", ["", "00000000", "4006381333932", "1234", "1" * 65, "４００６３８１３３３９３１", "http://example.test", "4006381333931\nextra"])
def test_invalid_barcodes_are_rejected(code):
    with pytest.raises(ValueError):
        normalize_barcode(code)


def test_scan_requires_login_and_csrf(client):
    assert client.get("/scan").status_code == 302
    login(client)
    assert client.post("/scan", data={"code": EAN}).status_code == 400
    assert client.post("/barcodes", data={"code": EAN}).status_code == 400


def test_unknown_scan_is_local_until_explicit_catalog_request(app, client):
    login(client)
    with patch("james.scan.fetch_suggestion") as fetch:
        result = scan_code(client)
        fetch.assert_not_called()
    assert result.status_code == 200
    assert "Einmal zuordnen" in result.text
    with app.app_context():
        assert db.session.scalar(select(func.count(HouseholdItem.id))) == 0


def test_new_registration_and_repeated_scan_do_not_buy_or_duplicate(app, client):
    login(client)
    assert register(client, item_name="Kaffee", brand="Marke", package_text="500 g", quantity="2").status_code == 200
    for _ in range(2):
        result = scan_code(client)
        assert "Kaffee" in result.text and "500 g" in result.text
    assert register(client).status_code == 200
    with app.app_context():
        assert db.session.scalar(select(func.count(HouseholdItem.id))) == 1
        assert db.session.scalar(select(func.count(Product.id))) == 1
        assert db.session.scalar(select(func.count(ProductBarcode.id))) == 1
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 0
        item = db.session.scalar(select(HouseholdItem))
        assert item.stock_status == "unknown"
        item_id = item.id
    assert action(client, item_id, "replenish", 1).status_code == 302
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2


def test_assign_existing_item_preserves_stock_and_default_quantity(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    assert register(client, item_id=str(item_id), quantity="999").status_code == 200
    with app.app_context():
        assert db.session.scalar(select(func.count(HouseholdItem.id))) == 1
        item = db.session.get(HouseholdItem, item_id)
        assert item.default_quantity == 2 and item.stock_status == "unknown"


def test_equivalent_code_does_not_duplicate_and_conflicting_reassignment_is_blocked(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    assert register(client, code=UPC).status_code == 200
    assert "Testprodukt" in scan_code(client, code="0" + UPC).text
    assert register(client, code="0" + UPC).status_code == 200
    assert register(client, code=UPC, item_id=str(item_id)).status_code == 409
    with app.app_context():
        assert db.session.scalar(select(func.count(ProductBarcode.id))) == 1


def test_household_isolation_for_scan_assignment_and_removal(app, client):
    other_id, other_home, _ = seed_item(app, "other@example.test")
    other = app.test_client()
    login(other, "other@example.test")
    register(other, product_name="Privates Fremdprodukt", item_id=str(other_id))
    with app.app_context():
        barcode_id = db.session.scalar(select(ProductBarcode.id))
    login(client)
    result = scan_code(client)
    assert "Einmal zuordnen" in result.text and "Privates Fremdprodukt" not in result.text
    assert register(client, item_id=str(other_id)).status_code == 404
    assert client.post(f"/barcodes/{barcode_id}/remove", data={"csrf_token": csrf(client, "/"), "version": 1}).status_code == 404
    assert register(client).status_code == 200
    with app.app_context():
        assert db.session.scalar(select(func.count(ProductBarcode.id))) == 2


def test_invalid_registration_rolls_back_new_article(app, client):
    login(client)
    assert register(client, quantity="0").status_code == 400
    assert register(client, code="123").status_code == 400
    with app.app_context():
        assert db.session.scalar(select(func.count(HouseholdItem.id))) == 0
        assert db.session.scalar(select(func.count(ProductBarcode.id))) == 0


def test_archived_article_is_found_but_must_be_restored(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    register(client, item_id=str(item_id))
    action(client, item_id, "archive", 1)
    result = scan_code(client)
    assert "Wieder aktivieren" in result.text and "+ Nachkaufen" not in result.text
    assert register(client, code=UPC, item_id=str(item_id)).status_code == 409


def test_removing_mapping_keeps_item_and_need_and_checks_version(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    register(client, item_id=str(item_id))
    action(client, item_id, "empty", 1)
    with app.app_context():
        barcode_id = db.session.scalar(select(ProductBarcode.id))
    assert "Gespeicherte Barcodes" in client.get(f"/items/{item_id}/edit").text
    payload = {"csrf_token": csrf(client, "/"), "version": 1}
    assert client.post(f"/barcodes/{barcode_id}/remove", data=payload).status_code == 409
    payload["version"] = 2
    assert client.post(f"/barcodes/{barcode_id}/remove", data=payload).status_code == 302
    assert "Einmal zuordnen" in scan_code(client).text
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2
        assert db.session.get(HouseholdItem, item_id).stock_status == "empty"


def test_catalog_is_opt_in_cached_and_does_not_overwrite_user_fields(app, client):
    login(client)
    suggestion = {"product_name": "Katalogname", "brand": "Katalogmarke", "package_text": "500 g"}
    with patch("james.scan.fetch_suggestion", return_value=suggestion) as fetch:
        result = scan_code(client, lookup="1", product_name="Mein Name")
        assert "Mein Name" in result.text and "Katalogmarke" in result.text
        assert "Open Food Facts" in result.text
        assert scan_code(client, lookup="1").status_code == 200
        assert fetch.call_count == 1
    with app.app_context():
        assert db.session.scalar(select(func.count(HouseholdItem.id))) == 0


def test_catalog_outage_preserves_manual_draft(client):
    login(client)
    with patch("james.scan.fetch_suggestion", side_effect=CatalogUnavailable("Bitte manuell erfassen.")):
        result = scan_code(client, lookup="1", product_name="Mein Entwurf", brand="Eigene Marke")
    assert result.status_code == 200 and "Mein Entwurf" in result.text and "Eigene Marke" in result.text


def test_catalogue_attribution_survives_confirmed_registration(app, client):
    login(client)
    result = register(client, data_source="openfoodfacts")
    assert result.status_code == 200 and "Open Food Facts" in result.text and "ODbL" in result.text
    with app.app_context():
        assert db.session.scalar(select(Product.data_source)) == "openfoodfacts"


def test_catalog_gate_and_negative_cache_expiry(app):
    with app.app_context():
        reserve_catalog_lookup()
        db.session.commit()
        with pytest.raises(CatalogUnavailable):
            reserve_catalog_lookup()
        db.session.rollback()
        gate = db.session.scalar(select(CatalogGate))
        gate.next_allowed_at = utcnow() - timedelta(seconds=1)
        db.session.commit()
        reserve_catalog_lookup()
        save_suggestion(normalize_barcode(EAN)[1], None)
        db.session.commit()
        assert cached_suggestion(normalize_barcode(EAN)[1]) == (True, None)


def test_camera_policy_is_limited_to_scanner(client):
    login(client)
    assert "camera=(self)" in client.get("/scan").headers["Permissions-Policy"]
    assert "camera=()" in client.get("/").headers["Permissions-Policy"]


class FakeResponse:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, maximum):
        return self.body[:maximum]


def test_catalog_http_uses_fixed_https_host_timeout_and_bounded_fields(app):
    with app.app_context(), patch("james.catalog.build_opener") as builder:
        builder.return_value.open.return_value = FakeResponse(b'{"product":{"product_name":"Test","brands":"Brand","quantity":"500 g"}}')
        result = fetch_suggestion(EAN)
        req = builder.return_value.open.call_args.args[0]
        assert req.full_url.startswith("https://world.openfoodfacts.org/api/v3/product/")
        assert req.get_header("User-agent").startswith("JamesPWA/")
        assert builder.return_value.open.call_args.kwargs["timeout"] == 3
        assert result == {"product_name": "Test", "brand": "Brand", "package_text": "500 g"}


@pytest.mark.parametrize("body", [b"not json", b"x" * 131073], ids=["invalid-json", "oversized"])
def test_catalog_rejects_invalid_or_oversized_responses(app, body):
    with app.app_context(), patch("james.catalog.build_opener") as builder:
        builder.return_value.open.return_value = FakeResponse(body)
        with pytest.raises(CatalogUnavailable):
            fetch_suggestion(EAN)


def test_catalog_timeout_and_not_found(app):
    with app.app_context(), patch("james.catalog.build_opener") as builder:
        builder.return_value.open.side_effect = URLError("offline")
        with pytest.raises(CatalogUnavailable):
            fetch_suggestion(EAN)
        builder.return_value.open.side_effect = HTTPError("https://world.openfoodfacts.org", 404, "missing", {}, None)
        assert fetch_suggestion(EAN) is None
