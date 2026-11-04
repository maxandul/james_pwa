"""Private user-driven browser connection. Network operations belong to worker."""
from datetime import timedelta

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select

from .extensions import db
from .models import Household, ShopBrowser, ShopLogin, utcnow
from .shop_login import account_bound
from .views import household_required

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


def profile():
    if g.membership.role != 'owner' or not account_bound(g.household.id):
        abort(403)
    item = db.session.scalar(select(ShopBrowser).where(ShopBrowser.household_id == g.household.id))
    empty = item and item.state == 'idle' and not item.context_id and not item.session_id
    if item and not empty and (item.user_id != current_user.id or item.auth_version != current_user.auth_version):
        abort(403)
    return item


@shop_browser.route('/shop-browser', methods=['GET', 'POST'])
@household_required
def index():
    if request.method == 'POST':
        db.session.execute(select(Household.id).where(Household.id == g.household.id).with_for_update())
    item = profile()
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
            if not item:
                item = ShopBrowser(household_id=g.household.id, user_id=current_user.id,
                                   auth_version=current_user.auth_version)
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
        return redirect(url_for('shop_browser.index'))
    from .shop_cart import PRODUCTS
    return render_template('shop_browser.html', profile=item, now=utcnow(), products=PRODUCTS)


@shop_browser.get('/shop-browser/live')
@household_required
def live():
    item = profile()
    if (not item or item.state != 'active' or not item.live_url
            or not item.expires_at or item.expires_at <= utcnow()):
        abort(410)
    # The provider adapter validates the exact HTTPS host before storage.
    return redirect(item.live_url)
