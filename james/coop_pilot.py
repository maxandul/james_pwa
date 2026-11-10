"""Explicit one-shot operator test using the ordinary household product model."""
from uuid import UUID, NAMESPACE_URL, uuid5

import click
from flask import current_app
from sqlalchemy import select

from .assortment import item_offers, lock_household, save_offer, save_product
from .extensions import db
from .models import PurchasePlan, PurchaseSource, ShopBrowser, ShopOffer, utcnow
from .planning import coop_preview, create_plan
from .services import Conflict, change_item, create_item

PRODUCTS = (
    {'name':'Spaghetti', 'product':'Barilla Spaghetti No. 5', 'brand':'Barilla',
     'package':'500 g', 'sku':'3032108', 'quantity':2,
     'url':'https://www.coop.ch/de/lebensmittel/vorraete/grundnahrungsmittel/teigwaren/spaghetti/barilla-spaghetti-no-5/p/3032108'},
    {'name':'Tomaten gehackt', 'product':'Prix Garantie Tomaten gehackt', 'brand':'Prix Garantie',
     'package':'400 g', 'sku':'6492579', 'quantity':1,
     'url':'https://www.coop.ch/de/lebensmittel/vorraete/konserven/gemuese/tomaten/prix-garantie-tomaten-gehackt/p/6492579'},
    {'name':'Salz mit Jod', 'product':'JuraSel Tafelsalz mit Jod', 'brand':'JuraSel',
     'package':'500 g', 'sku':'3020051', 'quantity':1,
     'url':'https://www.coop.ch/de/lebensmittel/vorraete/bouillons-gewuerze/salz-pfeffer/salz/jurasel-tafelsalz-mit-jod/p/3020051'},
)


def queue_plan(plan, profile, *, saved_login_authorized=False):
    from .shop_browser_worker import valid
    if (not current_app.config.get('SHOP_BROWSER_ENABLED') or not profile or not valid(profile)
            or profile.household_id != plan.household_id or profile.shop_key != 'coop'
            or not profile.context_id or (not profile.confirmed_at and not saved_login_authorized)):
        raise Conflict('Bitte zuerst die gespeicherte Coop-Anmeldung prüfen und das richtige Konto bestätigen.')
    preview = coop_preview(plan)
    if not preview['ready']:
        raise Conflict(' '.join(preview['problems']))
    if any(not 1 <= t['quantity'] <= 3 for t in preview['targets']):
        raise Conflict('Der kleine Test erlaubt höchstens drei Packungen je Produkt.')
    if plan.cart_state is not None:
        raise Conflict('Für dieses Vorhaben wurde bereits ein Warenkorbauftrag gestartet. Bitte das Ergebnis prüfen.')
    if db.session.scalar(select(PurchasePlan.id).where(PurchasePlan.household_id == plan.household_id,
            PurchasePlan.cart_state.in_(('queued','running')))):
        raise Conflict('Es läuft bereits ein Warenkorbauftrag für diesen Haushalt.')
    plan.cart_state = 'queued'
    plan.cart_requested_at = utcnow()
    plan.cart_actions = 0
    if profile.state == 'active' and profile.cart_state not in ('queued','running'):
        # Save the owner's manual session before opening the same context for
        # the authorized agent. Do not run two controllers in one browser.
        profile.state = 'closing'
        profile.live_url = None


def prepare_pilot(request_id, *, queue=False):
    request_id = str(UUID(request_id))
    bound = current_app.config.get('SHOP_BROWSER_HOUSEHOLD_ID') or current_app.config.get('GALAXUS_HOUSEHOLD_ID')
    try:
        home_id = int(bound)
    except (ValueError, TypeError):
        raise Conflict('Der Haushalt für den Shop-Test ist nicht gebunden.') from None
    lock_household(home_id)
    # Retained PurchasePlan.request_id is the durable receipt. Never replay a
    # prior test, including a crash, provider failure, or a later different job.
    existing = db.session.scalar(select(PurchasePlan).where(
        PurchasePlan.household_id == home_id, PurchasePlan.request_id == request_id))
    if existing:
        return existing, False
    profile = db.session.scalar(select(ShopBrowser).where(
        ShopBrowser.household_id == home_id, ShopBrowser.shop_key == 'coop'))
    from .shop_browser_worker import valid
    if not profile or not valid(profile) or not profile.context_id:
        raise Conflict('Die gespeicherte Coop-Anmeldung wurde noch nicht bestätigt.')
    source = db.session.scalar(select(PurchaseSource).where(
        PurchaseSource.household_id == home_id, PurchaseSource.shop_key == 'coop', PurchaseSource.active.is_(True)))
    if not source:
        raise Conflict('Bitte den Einkaufsort mit Coop verbinden.')
    chosen = []
    for target in PRODUCTS:
        if db.session.scalar(select(ShopOffer.id).where(ShopOffer.household_id == home_id,
                ShopOffer.source_id == source.id, ShopOffer.shop_sku == target['sku'])):
            raise Conflict('Ein Testprodukt ist bereits zugeordnet. Bitte die bestehende Zuordnung im Vorhaben verwenden.')
        item = create_item(home_id, {'name':f"[Coop-Test {request_id[:8]}] {target['name']}",
            'source':source.name, 'category':'Vorrat', 'unit':'Packung', 'quantity':'1'})
        product = save_product(home_id, item.id, {'product_name':target['product'],
            'brand':target['brand'], 'package_text':target['package']})
        product.data_source = 'delegated_test'
        db.session.flush()
        save_offer(home_id, item.id, product.id, {'source_id':str(source.id),
            'url':target['url'], 'shop_sku':target['sku'], 'units_per_pack':'1',
            'preferred':'1', 'confirm_exact':'1'})
        change_item(home_id, profile.user_id, item.id, 'extra',
            str(uuid5(NAMESPACE_URL, request_id + ':' + target['sku'])), item.version,
            quantity=str(target['quantity']))
        chosen.append((item, target))
    db.session.flush()
    review = {'request_id':request_id, 'source_version':source.version,
        'versions':{str(item.id):item.version for item, _ in chosen},
        'offers':{str(item.id):[[o.id,o.version,o.product.version] for o in item_offers(item)] for item, _ in chosen}}
    form = {f'include_{item.id}':'1' for item, _ in chosen}
    form.update({f'quantity_{item.id}':str(target['quantity']) for item, target in chosen})
    plan = create_plan(home_id, source.id, review, form)
    if queue:
        queue_plan(plan, profile, saved_login_authorized=True)
    return plan, True


def register_coop_cli(app):
    @app.cli.command('coop-cart-pilot')
    @click.option('--request-id', required=True, help='Stable UUID for exactly this authorized test.')
    @click.option('--queue', is_flag=True, help='Use the saved browser to run this authorized cart-only test.')
    @click.option('--authorize-test', is_flag=True)
    def pilot(request_id, queue, authorize_test):
        if not authorize_test:
            raise click.ClickException('Dieser Test benötigt einen ausdrücklichen Nutzerauftrag.')
        try:
            plan, created = prepare_pilot(request_id, queue=queue)
            db.session.commit()
        except (ValueError, Conflict) as exc:
            db.session.rollback()
            raise click.ClickException(str(exc)) from None
        click.echo(f'Coop-Test: Vorhaben {plan.id}; neu={created}; Auftrag={plan.cart_state or "vorbereitet"}.')
