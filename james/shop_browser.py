"""Private user-driven browser connection. Network operations belong to worker."""
from datetime import timedelta

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select

from .extensions import db
from .models import Household, ShopBrowser, ShopLogin, utcnow
from .views import household_required
from .shops import SHOPS

shop_browser = Blueprint('shop_browser', __name__)


@shop_browser.before_request
def enabled():
    if not current_app.config.get('SHOP_BROWSER_ENABLED'):
        abort(404)


@shop_browser.after_request
def private(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


def profile(shop_key='galaxus'):
    if shop_key not in SHOPS:
        abort(404)
    bound = current_app.config.get('SHOP_BROWSER_HOUSEHOLD_ID') or current_app.config.get('GALAXUS_HOUSEHOLD_ID')
    if g.membership.role != 'owner' or str(bound) != str(g.household.id):
        abort(403)
    item = db.session.scalar(select(ShopBrowser).where(ShopBrowser.household_id == g.household.id,
                                                      ShopBrowser.shop_key == shop_key))
    empty = item and item.state == 'idle' and not item.context_id and not item.session_id
    if item and not empty and (item.user_id != current_user.id or item.auth_version != current_user.auth_version):
        abort(403)
    return item


@shop_browser.route('/shop-browser', methods=['GET', 'POST'])
@shop_browser.route('/shop-browser/<shop_key>', methods=['GET', 'POST'])
@household_required
def index(shop_key='galaxus'):
    if request.method == 'POST':
        db.session.execute(select(Household.id).where(Household.id == g.household.id).with_for_update())
    item = profile(shop_key)
    if request.method == 'POST':
        action = request.form.get('action')
        if str(item.version if item else 0) != request.form.get('version'):
            abort(409)
        if action == 'open':
            if request.form.get('consent') != 'yes':
                abort(400)
            if item and (item.state != 'idle' or item.session_id):
                abort(409)
            if db.session.scalar(select(ShopLogin.id).where(ShopLogin.active_household_id == g.household.id)):
                abort(409)
            # One worker owns the CDP connection. Saved profiles may coexist,
            # active browsers may not (including unresolved creation/cleanup).
            if db.session.scalar(select(ShopBrowser.id).where(
                    ShopBrowser.household_id == g.household.id, ShopBrowser.shop_key != shop_key,
                    ShopBrowser.state != 'idle')):
                abort(409)
            if not item:
                item = ShopBrowser(household_id=g.household.id, user_id=current_user.id,
                                   auth_version=current_user.auth_version, shop_key=shop_key)
                db.session.add(item)
            item.user_id = current_user.id
            item.auth_version = current_user.auth_version
            item.state = 'queued'
            item.expires_at = utcnow() + timedelta(seconds=720)
            item.confirmed_at = None
            item.error_category = None
        elif action in ('close', 'forget'):
            if not item or item.state == 'creating':
                abort(409)
            if item.error_category == 'creation_unknown':
                # Provider creation must be reconciled before allowing another profile.
                abort(409)
            item.state = 'forgetting' if action == 'forget' else 'closing'
            item.live_url = None
        elif action == 'confirm':
            if not item or item.state != 'active' or not item.expires_at or item.expires_at <= utcnow():
                abort(409)
            item.confirmed_at = utcnow()
        elif action == 'cart':
            # Coop is connection + exact preview only in this first stage.
            if shop_key != 'galaxus':
                abort(400)
            if (not item or item.state != 'active' or not item.confirmed_at
                    or not item.expires_at or item.expires_at <= utcnow() + timedelta(seconds=180)
                    or item.cart_state in ('queued', 'running')):
                abort(409)
            if request.form.get('consent') != 'yes':
                abort(400)
            item.cart_state = 'queued'
            item.cart_actions = 0
        else:
            abort(400)
        db.session.commit()
        return redirect(url_for('shop_browser.index', **({'shop_key':shop_key} if shop_key != 'galaxus' else {})))
    from .shop_cart import PRODUCTS
    from .models import PurchaseSource
    source = db.session.scalar(select(PurchaseSource).where(PurchaseSource.household_id == g.household.id,
        PurchaseSource.shop_key == shop_key, PurchaseSource.active.is_(True)))
    from .models import PurchasePlan
    cart_plans = db.session.scalars(select(PurchasePlan).where(PurchasePlan.household_id == g.household.id,
        PurchasePlan.source_id == source.id, PurchasePlan.cart_state.is_not(None))
        .order_by(PurchasePlan.id.desc()).limit(5)).all() if shop_key == 'coop' and source else []
    return render_template('shop_browser.html', profile=item, now=utcnow(), products=PRODUCTS,
                           shop_key=shop_key, shop=SHOPS[shop_key], source=source, cart_plans=cart_plans)


@shop_browser.get('/shop-browser/live')
@shop_browser.get('/shop-browser/<shop_key>/live')
@household_required
def live(shop_key='galaxus'):
    item = profile(shop_key)
    if (not item or item.state != 'active' or not item.live_url
            or not item.expires_at or item.expires_at <= utcnow()):
        abort(410)
    # The provider adapter validates the exact HTTPS host before storage.
    return redirect(item.live_url)


@shop_browser.route('/shop-browser/coop/preview/<int:plan_id>', methods=['GET','POST'])
@household_required
def preview(plan_id):
    if request.method == 'POST':
        db.session.execute(select(Household.id).where(Household.id == g.household.id).with_for_update())
    browser = profile('coop')
    from .models import PurchasePlan
    from .planning import coop_preview
    plan = db.session.scalar(select(PurchasePlan).where(PurchasePlan.id == plan_id,
        PurchasePlan.household_id == g.household.id))
    if not plan:
        abort(404)
    error, status = None, 200
    if request.method == 'POST':
        from .coop_pilot import queue_plan
        from .assortment import version_matches
        from .services import Conflict
        try:
            version_matches(plan, request.form.get('version'))
            if request.form.get('consent') != 'yes':
                raise ValueError('Bitte den konkreten Warenkorbtest bestätigen.')
            queue_plan(plan, browser)
            db.session.commit()
            return redirect(url_for('shop_browser.preview', plan_id=plan.id))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), 409 if isinstance(exc, Conflict) else 400
    return render_template('coop_preview.html', plan=plan, error=error, **coop_preview(plan)), status


@shop_browser.route('/shop-browser/coop/pilot', methods=['GET','POST'])
@household_required
def pilot():
    from uuid import UUID, uuid4
    from .coop_pilot import PRODUCTS, prepare_pilot
    from .services import Conflict
    profile('coop')
    error, status = None, 200
    request_id = request.form.get('request_id', '') if request.method == 'POST' else str(uuid4())
    if request.method == 'POST':
        try:
            if request.form.get('consent') != 'yes':
                raise ValueError('Bitte den konkreten Warenkorbtest bestätigen.')
            try:
                request_id = str(UUID(request_id))
            except ValueError:
                raise ValueError('Bitte die Testseite neu laden.') from None
            plan, _ = prepare_pilot(request_id, queue=True)
            db.session.commit()
            return redirect(url_for('shop_browser.preview', plan_id=plan.id))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), 409 if isinstance(exc, Conflict) else 400
    return render_template('coop_pilot.html', products=PRODUCTS, request_id=request_id, error=error), status
