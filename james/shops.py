"""Shop identity and exact-product checks shared by UI and future shop jobs."""
import hashlib
import json
import re
from urllib.parse import urlsplit

SHOPS = {
    'galaxus': {'name': 'Galaxus', 'start_url': 'https://www.galaxus.ch/'},
    'coop': {'name': 'Coop', 'start_url': 'https://www.coop.ch/de/'},
}


def coop_product_id(url):
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'www.coop.ch'
                or parsed.query or parsed.fragment):
            return None
        match = re.fullmatch(r'/(?:de|fr|it)/[^?#]*/p/([0-9]+)/?', parsed.path)
        return match[1] if match else None
    except ValueError:
        return None


def offer_identity(offer):
    """All values that affect the identity or pack conversion, excluding labels."""
    return {
        'shop_key': offer.source.shop_key, 'source_id': offer.source_id,
        'offer_id': offer.id, 'product_id': offer.product_id,
        'product_version': offer.product.version, 'item_id': offer.product.item_id,
        'name': offer.product.name, 'brand': offer.product.brand,
        'package_text': offer.product.package_text, 'url': offer.url,
        'shop_sku': offer.shop_sku, 'units_per_pack': format(offer.units_per_pack.normalize(), 'f'),
        'unit': offer.product.item.unit,
    }


def offer_signature(offer):
    return hashlib.sha256(json.dumps(offer_identity(offer), sort_keys=True,
        ensure_ascii=False).encode()).hexdigest()


def offer_problems(offer, *, require_confirmation=True):
    problems = []
    if not offer.active or not offer.source.active or offer.product.item.archived:
        problems.append('Produkt oder Einkaufsort ist inaktiv.')
    if offer.source.shop_key != 'coop':
        problems.append('Der Einkaufsort ist nicht mit Coop verbunden.')
    if not offer.product.package_text.strip():
        problems.append('Die genaue Packungsangabe fehlt.')
    if not re.fullmatch(r'[0-9]+', offer.shop_sku or ''):
        problems.append('Eine gültige Coop-Artikelnummer fehlt.')
    if not coop_product_id(offer.url) or coop_product_id(offer.url) != offer.shop_sku:
        problems.append('Coop-Produktlink und Artikelnummer müssen übereinstimmen. Bitte einen Produktlink ohne Zusatzparameter verwenden.')
    if require_confirmation and (not offer.confirmed_at or offer.confirmed_signature != offer_signature(offer)):
        problems.append('Die genaue Variante, Packung und Umrechnung müssen erneut bestätigt werden.')
    return problems
