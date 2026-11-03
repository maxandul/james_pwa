"""Household-serialized shopping reservations; preparing never books a purchase."""
from decimal import Decimal, ROUND_CEILING

from flask import abort
from sqlalchemy import select

from .assortment import item_offers, lock_household, selected_offer, shopping_options, version_matches
from .extensions import db
from .models import HouseholdItem, PurchasePlan, PurchaseSource, ShoppingNeed
from .services import Conflict, positive_int

ACTIVE = ('draft', 'ordered')


def active_plans(household_id):
    return db.session.scalars(select(PurchasePlan).where(PurchasePlan.household_id == household_id,
        PurchasePlan.state.in_(ACTIVE)).order_by(PurchasePlan.id)).all()


def reservations(household_id):
    quantities = {}
    for plan in active_plans(household_id):
        for line in plan.lines:
            quantities[line['item_id']] = quantities.get(line['item_id'], 0) + line['reserved']
    return quantities


def clamp_reservations(item, need):
    """Completed/removed demand cannot silently reserve future replenishments."""
    remaining = need.quantity
    for plan in active_plans(item.household_id):
        lines, changed = [], False
        for original in plan.lines:
            line = dict(original)
            if line['item_id'] == item.id:
                amount = min(line['reserved'], remaining)
                remaining -= amount
                changed |= amount != line['reserved']
                line['reserved'] = amount
            lines.append(line)
        if changed:
            plan.lines = lines


def candidates(household_id, source):
    rows = db.session.execute(select(HouseholdItem, ShoppingNeed).join(ShoppingNeed).where(
        HouseholdItem.household_id == household_id, HouseholdItem.archived.is_(False), ShoppingNeed.quantity > 0
    ).order_by(HouseholdItem.name)).all()
    allowed, _ = shopping_options(rows)
    reserved = reservations(household_id)
    return [(item, need, max(0, need.quantity - reserved.get(item.id, 0)))
        for item, need in rows if source.name in allowed[item.id]]


def create_plan(household_id, source_id, review, data):
    lock_household(household_id)
    source = db.session.scalar(select(PurchaseSource).where(PurchaseSource.id == source_id,
        PurchaseSource.household_id == household_id).execution_options(populate_existing=True))
    if not source or not source.active:
        abort(404)
    existing = db.session.scalar(select(PurchasePlan).where(PurchasePlan.household_id == household_id,
        PurchasePlan.request_id == review['request_id']))
    if existing:
        return existing
    version_matches(source, review.get('source_version'))
    try:
        requested = {int(key.removeprefix('include_')) for key, value in data.items()
            if key.startswith('include_') and value == '1'}
    except ValueError:
        raise ValueError('Bitte gueltige Artikel auswaehlen.') from None
    rows = candidates(household_id, source)
    if not requested.issubset({item.id for item, _, _ in rows}):
        raise Conflict('Ein ausgewaehlter Artikel ist nicht mehr offen oder fuer diesen Laden verfuegbar. Bitte neu pruefen.')
    lines = []
    for item, need, available in rows:
        if data.get(f'include_{item.id}') != '1':
            continue
        version_matches(item, review.get('versions', {}).get(str(item.id)))
        quantity = positive_int(data.get(f'quantity_{item.id}'))
        if quantity > available:
            raise Conflict('Ein Teil der Menge wurde inzwischen eingeplant oder erledigt. Bitte neu pruefen.')
        choice = selected_offer([offer for offer in item_offers(item) if offer.active], source.name, quantity)
        offer = choice.get('offer')
        if review.get('offers', {}).get(str(item.id)) != [[entry.id, entry.version, entry.product.version] for entry in item_offers(item)]:
            raise Conflict('Die Produktzuordnung wurde inzwischen geaendert. Bitte neu pruefen.')
        lines.append({'item_id': item.id, 'name': item.name, 'unit': item.unit,
            'quantity': quantity, 'reserved': quantity,
            'product': offer.product.name if offer else '', 'url': offer.url if offer else '',
            'units_per_pack': str(offer.units_per_pack) if offer else None})
    if not lines:
        raise ValueError('Bitte mindestens einen noch verfuegbaren Artikel auswaehlen.')
    plan = PurchasePlan(household_id=household_id, source_id=source.id,
        request_id=review['request_id'], lines=lines)
    db.session.add(plan)
    db.session.flush()
    return plan


def change_plan(household_id, plan_id, version, action, reference=''):
    lock_household(household_id)
    plan = db.session.scalar(select(PurchasePlan).where(PurchasePlan.id == plan_id,
        PurchasePlan.household_id == household_id).with_for_update().execution_options(populate_existing=True))
    if not plan:
        abort(404)
    version_matches(plan, version)
    allowed = {'ordered': ('draft',), 'closed': ACTIVE, 'cancelled': ACTIVE}
    if action not in allowed or plan.state not in allowed[action]:
        raise Conflict('Diese Statusaenderung ist nicht mehr moeglich. Bitte neu laden.')
    if len(reference) > 100 or any(ord(c) < 32 for c in reference):
        raise ValueError('Bitte eine kurze Bestellreferenz ohne Zeilenumbrueche verwenden.')
    plan.state = action
    if action == 'ordered':
        plan.reference = reference.strip()
    return plan


def line_description(line):
    quantity = line['reserved']
    text = f"{quantity} {line['unit']} {line['name']}"
    if line['product']:
        units = Decimal(line['units_per_pack'])
        packs = int((Decimal(quantity) / units).to_integral_value(rounding=ROUND_CEILING))
        covered = packs * units
        text += f" – {line['product']}: {packs} Packung(en), {covered.normalize():f} {line['unit']}"
    else:
        text += ' – Produkt im Shop noch auswaehlen'
    return text
