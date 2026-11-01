"""Trade-item barcodes and household-local product assignments."""
import re

from flask import abort
from sqlalchemy import select

from .extensions import db
from .models import Household, HouseholdItem, Product, ProductBarcode
from .services import Conflict, clean_text, create_item


def normalize_barcode(value):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("Bitte einen gueltigen EAN-/GTIN-Code eingeben.")
    code = value.strip().replace(" ", "")
    if len(code) not in {8, 12, 13, 14} or not re.fullmatch(r"[0-9]+", code) or not int(code):
        raise ValueError("Der Barcode braucht 8, 12, 13 oder 14 Ziffern.")
    checksum = (-sum(int(digit) * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(reversed(code[:-1])))) % 10
    if checksum != int(code[-1]):
        raise ValueError("Die Pruefziffer stimmt nicht. Bitte den Barcode nochmals pruefen.")
    return code, code.zfill(14)


def find_barcode(household_id, value):
    code, gtin = normalize_barcode(value)
    return db.session.scalar(select(ProductBarcode).join(Product).join(HouseholdItem).where(
        ProductBarcode.household_id == household_id, ProductBarcode.gtin == gtin,
        Product.household_id == household_id, HouseholdItem.household_id == household_id))


def register_barcode(household_id, data):
    code, gtin = normalize_barcode(data.get("code", ""))
    # Covers first-time assignment races, including two simultaneous new articles.
    db.session.scalar(select(Household).where(Household.id == household_id).with_for_update())
    known = find_barcode(household_id, code)
    target = data.get("item_id", "new")
    if known:
        if target != "new" and str(known.product.item_id) != str(target):
            raise Conflict("Dieser Barcode ist bereits einem anderen Artikel zugeordnet. Bitte die bestehende Zuordnung zuerst entfernen.")
        return known, False
    name = clean_text(data.get("product_name"), "Produktname", 200)
    brand = clean_text(data.get("brand"), "Marke", 100) if data.get("brand", "").strip() else ""
    package = clean_text(data.get("package_text"), "Packungsangabe", 80) if data.get("package_text", "").strip() else ""
    if target == "new":
        item = create_item(household_id, {"name": data.get("item_name", "").strip() or name[:100],
            "category": data.get("category") or "Vorrat", "source": data.get("source") or "Laden",
            "quantity": data.get("quantity") or "1", "unit": data.get("unit") or "Packung",
            "favorite": data.get("favorite", "0")})
    else:
        try:
            target_id = int(target)
        except (TypeError, ValueError):
            raise ValueError("Bitte einen Artikel aus eurem Haushalt waehlen.") from None
        item = db.session.scalar(select(HouseholdItem).where(
            HouseholdItem.id == target_id, HouseholdItem.household_id == household_id).with_for_update())
        if not item:
            abort(404)
        if item.archived:
            raise Conflict("Dieser Artikel ist archiviert. Bitte zuerst wieder aktivieren.")
    source = data.get("data_source", "manual")
    if source not in {"manual", "openfoodfacts", "openfoodfacts_staging"}:
        source = "manual"
    product = Product(household_id=household_id, item_id=item.id, name=name, brand=brand, package_text=package, data_source=source)
    db.session.add(product)
    db.session.flush()
    barcode = ProductBarcode(household_id=household_id, product_id=product.id, code=code, gtin=gtin)
    db.session.add(barcode)
    db.session.flush()
    return barcode, True


def remove_barcode(household_id, barcode_id, expected_version):
    barcode = db.session.scalar(select(ProductBarcode).join(Product).where(
        ProductBarcode.id == barcode_id, ProductBarcode.household_id == household_id,
        Product.household_id == household_id).with_for_update())
    if not barcode:
        abort(404)
    item = db.session.scalar(select(HouseholdItem).where(
        HouseholdItem.id == barcode.product.item_id, HouseholdItem.household_id == household_id).with_for_update())
    if not item:
        abort(404)
    try:
        matches = int(expected_version) == item.version
    except (TypeError, ValueError):
        matches = False
    if not matches:
        raise Conflict("Der Artikel wurde inzwischen geaendert. Bitte neu laden.")
    # Mapping is independent of inventory; keep the product and article intact.
    db.session.delete(barcode)
    return item.id
