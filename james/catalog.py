"""Opt-in, read-only Open Food Facts suggestions; no photos or household data."""
import base64
import json
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from flask import current_app
from sqlalchemy import select

from .barcodes import normalize_barcode
from .extensions import db
from .models import CatalogCache, CatalogGate, utcnow


class CatalogUnavailable(ValueError):
    pass


def cached_suggestion(gtin):
    key = current_app.config["OPENFOODFACTS_ENVIRONMENT"] + ":" + gtin
    entry = db.session.get(CatalogCache, key)
    if entry and entry.expires_at > utcnow():
        return True, entry.payload
    return False, None


def reserve_catalog_lookup():
    """Caller commits this reservation BEFORE HTTP, releasing the DB row lock."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.engine.dialect.name == "postgresql" else sqlite_insert
    key = current_app.config["OPENFOODFACTS_ENVIRONMENT"]
    now = utcnow()
    db.session.execute(insert(CatalogGate).values(key=key, next_allowed_at=now)
        .on_conflict_do_nothing(index_elements=[CatalogGate.key]))
    gate = db.session.scalar(select(CatalogGate).where(CatalogGate.key == key).with_for_update())
    if gate.next_allowed_at > now:
        raise CatalogUnavailable("Bitte einige Sekunden warten. Du kannst das Produkt auch direkt selbst erfassen.")
    # <= 12 requests/minute across workers, below the documented 15/minute limit.
    gate.next_allowed_at = now + timedelta(seconds=5)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_suggestion(value):
    code, gtin = normalize_barcode(value)
    environment = current_app.config["OPENFOODFACTS_ENVIRONMENT"]
    host = "world.openfoodfacts.net" if environment == "staging" else "world.openfoodfacts.org"
    url = f"https://{host}/api/v3/product/{code}?" + urlencode({"fields": "product_name,product_name_de,brands,quantity"})
    headers = {"Accept": "application/json", "User-Agent": current_app.config["OPENFOODFACTS_USER_AGENT"]}
    if environment == "staging":
        # Public staging access credentials documented by Open Food Facts.
        headers["Authorization"] = "Basic " + base64.b64encode(b"off:off").decode()
    try:
        with build_opener(NoRedirect()).open(Request(url, headers=headers), timeout=3) as response:
            body = response.read(131073)
            if len(body) > 131072:
                raise CatalogUnavailable("Der Produktkatalog ist gerade nicht verfügbar. Bitte manuell erfassen.")
            data = json.loads(body)
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise CatalogUnavailable("Der Produktkatalog ist gerade nicht verfügbar. Bitte manuell erfassen.") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise CatalogUnavailable("Der Produktkatalog ist gerade nicht verfügbar. Bitte manuell erfassen.") from None
    product = data.get("product") if isinstance(data, dict) else None
    if not isinstance(product, dict):
        return None
    def text(field, limit):
        value = product.get(field)
        return " ".join(value.split())[:limit] if isinstance(value, str) else ""
    name = text("product_name_de", 200) or text("product_name", 200)
    if not name:
        return None
    return {"product_name": name, "brand": text("brands", 100), "package_text": text("quantity", 80)}


def save_suggestion(gtin, payload):
    key = current_app.config["OPENFOODFACTS_ENVIRONMENT"] + ":" + gtin
    entry = db.session.get(CatalogCache, key)
    if not entry:
        entry = CatalogCache(key=key)
        db.session.add(entry)
    entry.payload = payload
    entry.expires_at = utcnow() + (timedelta(days=1) if payload else timedelta(hours=1))
