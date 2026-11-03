"""Household-owned categories, purchase sources, variants and shop offers."""
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from unicodedata import normalize
from urllib.parse import urlsplit

from flask import abort
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from .extensions import db
from .models import Category, Household, HouseholdItem, ItemSource, Product, ProductBarcode, PurchaseSource, ShopOffer
from .services import Conflict, clean_text

CATEGORIES = ("Vorrat", "Frisches", "Getraenke", "Haushalt", "Pflege", "Tierbedarf")
SOURCES = ("Laden", "Coop", "Migros", "Galaxus")
KINDS = {"category": Category, "source": PurchaseSource}


def key(value):
    return normalize("NFKC", value).casefold()


def lock_household(household_id):
    db.session.scalar(select(Household).where(Household.id == household_id).with_for_update())


def entries(household_id, kind):
    model = KINDS[kind]
    return db.session.scalars(select(model).where(model.household_id == household_id).order_by(model.name)).all()


def resolve(household_id, kind, value):
    name = clean_text(value, "Bezeichnung", 60)
    name_key = key(name)
    return next((entry for entry in entries(household_id, kind)
        if entry.name_key == name_key or name_key in entry.aliases), None)


def ensure_entry(household_id, kind, value):
    existing = resolve(household_id, kind, value)
    if existing:
        return existing
    name = clean_text(value, "Bezeichnung", 60)
    entry = KINDS[kind](household_id=household_id, name=name, name_key=key(name), aliases=[])
    db.session.add(entry)
    db.session.flush([entry])
    return entry


def ensure_defaults(household_id):
    for kind, names in (("category", CATEGORIES), ("source", SOURCES)):
        known = {name_key for entry in entries(household_id, kind) for name_key in [entry.name_key, *entry.aliases]}
        for name in names:
            if key(name) not in known:
                ensure_entry(household_id, kind, name)


def canonical_labels(household_id, category, source):
    ensure_defaults(household_id)
    return (ensure_entry(household_id, "category", category).name,
        ensure_entry(household_id, "source", source).name)


def version_matches(entry, value):
    try:
        valid = int(value) == entry.version
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise Conflict("Die Daten wurden inzwischen geaendert. Bitte neu laden.")


def save_entry(household_id, kind, name, entry_id=None, version=None):
    if kind not in KINDS:
        abort(404)
    lock_household(household_id)
    name = clean_text(name, "Bezeichnung", 60)
    collision = resolve(household_id, kind, name)
    if entry_id is None:
        if collision:
            raise Conflict("Diese Bezeichnung ist bereits vorhanden.")
        return ensure_entry(household_id, kind, name)
    model = KINDS[kind]
    entry = db.session.scalar(select(model).where(model.id == entry_id, model.household_id == household_id))
    if not entry:
        abort(404)
    version_matches(entry, version)
    if collision and collision.id != entry.id:
        raise Conflict("Diese Bezeichnung wird bereits verwendet.")
    former_keys = set(entry.aliases) | {entry.name_key}
    column = HouseholdItem.category if kind == "category" else HouseholdItem.source
    items = db.session.scalars(select(HouseholdItem).where(HouseholdItem.household_id == household_id).with_for_update()).all()
    for item in items:
        if key(getattr(item, column.key)) in former_keys:
            setattr(item, column.key, name)
            item.version += 1
    entry.name = name
    entry.name_key = key(name)
    entry.aliases = sorted(former_keys - {entry.name_key})
    entry.version += 1
    return entry


def source_ids(item):
    return list(db.session.scalars(select(ItemSource.source_id).join(PurchaseSource).where(
        ItemSource.item_id == item.id, PurchaseSource.household_id == item.household_id).order_by(ItemSource.source_id)))


def offer_source_ids(item):
    return set(db.session.scalars(select(ShopOffer.source_id).join(Product).join(PurchaseSource).where(
        Product.item_id == item.id, Product.household_id == item.household_id,
        ShopOffer.household_id == item.household_id, PurchaseSource.household_id == item.household_id,
        ShopOffer.active.is_(True))))


def sync_sources(item, data=None, restore_ids=None):
    preferred = ensure_entry(item.household_id, "source", item.source)
    selected = set(source_ids(item))
    if restore_ids is not None:
        selected = set(restore_ids)
    elif data and data.get("sources_present") == "1":
        values = data.getlist("source_ids") if hasattr(data, "getlist") else data.get("source_ids", [])
        try:
            selected = {int(value) for value in values}
        except (TypeError, ValueError):
            raise ValueError("Bitte gueltige Einkaufsorte waehlen.") from None
    selected |= {preferred.id} | offer_source_ids(item)
    valid = {entry.id for entry in entries(item.household_id, "source")}
    if not selected.issubset(valid):
        raise ValueError("Bitte nur Einkaufsorte aus eurem Haushalt waehlen.")
    links = db.session.scalars(select(ItemSource).where(ItemSource.item_id == item.id)).all()
    existing = {link.source_id for link in links}
    for link in links:
        if link.source_id not in selected:
            db.session.delete(link)
    for source_id in selected - existing:
        db.session.add(ItemSource(item_id=item.id, source_id=source_id))


def get_item(household_id, item_id):
    item = db.session.scalar(select(HouseholdItem).where(
        HouseholdItem.id == item_id, HouseholdItem.household_id == household_id).with_for_update().execution_options(populate_existing=True))
    if not item:
        abort(404)
    if item.archived:
        raise Conflict("Der Artikel ist archiviert. Bitte zuerst wieder aktivieren.")
    return item


def item_products(item):
    return db.session.scalars(select(Product).where(
        Product.item_id == item.id, Product.household_id == item.household_id).order_by(Product.name)).all()


def item_offers(item):
    return db.session.scalars(select(ShopOffer).join(Product).join(PurchaseSource).where(
        Product.item_id == item.id, Product.household_id == item.household_id,
        ShopOffer.household_id == item.household_id, PurchaseSource.household_id == item.household_id
    ).order_by(PurchaseSource.name, Product.name)).all()


def save_product(household_id, item_id, data, product_id=None):
    lock_household(household_id)
    item = get_item(household_id, item_id)
    product = db.session.scalar(select(Product).where(Product.id == product_id,
        Product.household_id == household_id, Product.item_id == item_id)) if product_id else None
    if product_id and not product:
        abort(404)
    if product:
        version_matches(product, data.get("version"))
    else:
        product = Product(household_id=household_id, item_id=item.id)
        db.session.add(product)
    product.name = clean_text(data.get("product_name"), "Produktname", 200)
    product.brand = clean_text(data["brand"], "Marke", 100) if data.get("brand", "").strip() else ""
    product.package_text = clean_text(data["package_text"], "Packungsangabe", 80) if data.get("package_text", "").strip() else ""
    db.session.flush()
    code = data.get("code", "").strip()
    if code:
        from .barcodes import find_barcode, normalize_barcode
        code, gtin = normalize_barcode(code)
        known = find_barcode(household_id, code)
        if known and known.product_id != product.id:
            raise Conflict("Dieser Barcode gehoert bereits zu einem anderen Produkt.")
        if not known:
            db.session.add(ProductBarcode(household_id=household_id, product_id=product.id, code=code, gtin=gtin))
    return product


def pack_units(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not 0 < number <= 999999 or number != number.quantize(Decimal("0.001")):
            raise ValueError()
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Packungsinhalt: positive Menge mit hoechstens drei Nachkommastellen eingeben.") from None
    return number


def safe_url(value):
    value = value.strip()
    if not value:
        return ""
    value = clean_text(value, "Produktlink", 1000)
    try:
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.port not in {None, 443}:
            raise ValueError()
    except ValueError:
        raise ValueError("Bitte einen HTTPS-Produktlink ohne Zugangsdaten eingeben.") from None
    return value


def save_offer(household_id, item_id, product_id, data, offer_id=None, *, expected_unit=None):
    lock_household(household_id)
    item = get_item(household_id, item_id)
    product = db.session.scalar(select(Product).where(Product.id == product_id,
        Product.household_id == household_id, Product.item_id == item_id))
    if not product:
        abort(404)
    try:
        source_id = int(data.get("source_id"))
    except (TypeError, ValueError):
        raise ValueError("Bitte einen Einkaufsort waehlen.") from None
    source = db.session.scalar(select(PurchaseSource).where(
        PurchaseSource.id == source_id, PurchaseSource.household_id == household_id))
    if not source:
        raise ValueError("Bitte einen Einkaufsort aus eurem Haushalt waehlen.")
    if expected_unit is not None and expected_unit != item.unit:
        raise Conflict("Die Artikeleinheit wurde geaendert. Bitte neu laden und den Packungsinhalt erneut pruefen.")
    offer = db.session.get(ShopOffer, offer_id) if offer_id else None
    if offer_id:
        if not offer or offer.household_id != household_id or offer.product_id != product_id:
            abort(404)
        version_matches(offer, data.get("version"))
    elif db.session.scalar(select(ShopOffer.id).where(ShopOffer.product_id == product_id, ShopOffer.source_id == source_id)):
        raise Conflict("Dieses Produkt ist hier bereits hinterlegt. Bitte das vorhandene Angebot bearbeiten.")
    else:
        offer = ShopOffer(household_id=household_id, product_id=product_id)
        db.session.add(offer)
    duplicate = db.session.scalar(select(ShopOffer.id).where(
        ShopOffer.product_id == product_id, ShopOffer.source_id == source_id,
        ShopOffer.id != offer.id)) if offer_id else None
    if duplicate:
        raise Conflict("Dieses Produkt ist hier bereits hinterlegt. Bitte das vorhandene Angebot bearbeiten.")
    offer.source_id = source_id
    offer.units_per_pack = pack_units(data.get("units_per_pack", "1"))
    offer.url = safe_url(data.get("url", ""))
    offer.shop_sku = clean_text(data["shop_sku"], "Shop-Artikelnummer", 80) if data.get("shop_sku", "").strip() else ""
    offer.preferred = data.get("preferred") == "1"
    offer.active = data.get("active", "1") == "1"
    if offer.preferred and offer.active:
        for other in item_offers(item):
            if other.id != offer.id and other.source_id == source_id:
                other.preferred = False
    db.session.flush()
    sync_sources(item)
    return offer


def shopping_options(rows):
    """One need can appear under several sources; it is never duplicated in the DB."""
    if not rows:
        return {}, {}
    household_id = rows[0][0].household_id
    items = {item.id: item for item, need in rows}
    known = entries(household_id, 'source')
    allowed = {}
    for item in items.values():
        preference = next((entry for entry in known if key(item.source) in {entry.name_key, *entry.aliases}), None)
        allowed[item.id] = {preference.name if preference else item.source}
    links = db.session.execute(select(ItemSource.item_id, PurchaseSource.name).join(PurchaseSource).where(
        ItemSource.item_id.in_(items), PurchaseSource.household_id == household_id)).all()
    for item_id, name in links:
        allowed[item_id].add(name)
    offers = {item_id: [] for item_id in items}
    active = db.session.scalars(select(ShopOffer).join(Product).join(PurchaseSource).options(
        joinedload(ShopOffer.product), joinedload(ShopOffer.source)).where(
        Product.item_id.in_(items), Product.household_id == household_id,
        ShopOffer.household_id == household_id, PurchaseSource.household_id == household_id,
        ShopOffer.active.is_(True)).order_by(PurchaseSource.name, Product.name, ShopOffer.id)).all()
    for offer in active:
        item_id = offer.product.item_id
        offers[item_id].append(offer)
        allowed[item_id].add(offer.source.name)
    return allowed, offers


def selected_offer(offers, source, quantity):
    candidates = [offer for offer in offers if offer.source.name == source]
    preferred = [offer for offer in candidates if offer.preferred]
    choice = preferred[0] if len(preferred) == 1 else candidates[0] if len(candidates) == 1 else None
    if not choice:
        return {"offer": None, "multiple": len(candidates) > 1}
    packs = int((Decimal(quantity) / choice.units_per_pack).to_integral_value(rounding=ROUND_CEILING))
    return {"offer": choice, "packs": packs, "covered": packs * choice.units_per_pack, "multiple": False}
