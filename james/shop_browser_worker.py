"""Single-replica worker holding CDP open during the user's manual login."""
from time import monotonic, sleep
from flask import current_app

from sqlalchemy import select, update

from .extensions import db
from .models import ShopBrowser, User, utcnow
from .services import membership_for
from scripts.shop_browser_context import Browserbase, BrowserUnavailable, identifier
from .shops import SHOPS
from .models import PurchasePlan, Household, ShopLogin
from datetime import timedelta


def valid(item):
    user = db.session.get(User, item.user_id, populate_existing=True)
    member = membership_for(item.user_id)
    return bool(user and user.active and user.auth_version == item.auth_version and member
                and member.role == 'owner' and member.household_id == item.household_id
                and item.shop_key in SHOPS)


def set_fields(pid, **values):
    # UI version checks must also detect worker state transitions.
    db.session.execute(update(ShopBrowser).where(ShopBrowser.id == pid)
                       .values(**values, version=ShopBrowser.version + 1))
    db.session.commit()


def session_status(provider, sid):
    try:
        return provider.session(sid)['status']
    except BrowserUnavailable as exc:
        if exc.status == 404:
            return 'MISSING'
        raise


def finish(provider, pid, *, forget=False, pause=sleep):
    db.session.expire_all()
    item = db.session.get(ShopBrowser, pid)
    sid, context = item.session_id, item.context_id
    db.session.rollback()
    if sid:
        current_app.logger.warning('Shopbrowser cleanup phase: session')
        terminal = ('COMPLETED', 'TIMED_OUT', 'ERROR', 'MISSING')
        status = session_status(provider, sid)
        if status not in terminal:
            try:
                provider.release(sid)
            except BrowserUnavailable as exc:
                # A release can race provider expiry; verify absence with GET.
                if exc.status != 404 or session_status(provider, sid) not in terminal:
                    raise
        for _ in range(10):
            if session_status(provider, sid) in terminal:
                break
            pause(1)
        else:
            raise BrowserUnavailable('cleanup_pending')
        pause(5)
    # Read the latest request; a forget request must not be lost during release.
    db.session.expire_all()
    item = db.session.get(ShopBrowser, pid)
    forget = forget or item.state == 'forgetting' or not valid(item)
    interrupted = item.cart_state in ('queued', 'running')
    plan_id = item.cart_plan_id
    db.session.rollback()
    if forget and context:
        current_app.logger.warning('Shopbrowser cleanup phase: context')
        try:
            provider.delete_context(context)
        except BrowserUnavailable as exc:
            if exc.status != 404:
                raise
    set_fields(pid, session_id=None, live_url=None, state='idle', error_category=None,
               **({'cart_state': 'INTERRUPTED'} if interrupted else {}),
               **({'context_id': None, 'confirmed_at': None} if forget else {}))
    if interrupted and plan_id:
        db.session.execute(update(PurchasePlan).where(PurchasePlan.id == plan_id,
            PurchasePlan.cart_state == 'running').values(cart_state='INTERRUPTED', version=PurchasePlan.version+1))
        db.session.commit()
    current_app.logger.warning('Shopbrowser cleanup complete: forgotten=%s', forget)


def connect(provider, pid):
    # Claimed queued job is never automatically retried after a crash.
    item = db.session.get(ShopBrowser, pid)
    context = item.context_id
    start_url = SHOPS[item.shop_key]['start_url']
    db.session.rollback()
    if not context:
        context = provider.create_context()
        set_fields(pid, context_id=context)
    session = provider.create_session(context, keep_alive=False)
    sid = identifier(session['id'])
    set_fields(pid, session_id=sid)
    live_url = provider.live_url(sid)
    # All provider exceptions are redacted by the caller; no CDP URLs in logs.
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(session['connectUrl'], timeout=20000)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(start_url, wait_until='domcontentloaded', timeout=30000)
        db.session.expire_all()
        item = db.session.get(ShopBrowser, pid)
        if not valid(item) or item.expires_at <= utcnow():
            db.session.rollback()
            finish(provider, pid, forget=not valid(item))
            return
        set_fields(pid, state='active', live_url=live_url)
        until = monotonic() + 720
        while monotonic() < until:
            db.session.expire_all()
            item = db.session.get(ShopBrowser, pid)
            stop = item.state != 'active' or item.expires_at <= utcnow() or not valid(item)
            forget = item.state == 'forgetting' or not valid(item)
            db.session.rollback()
            if stop:
                finish(provider, pid, forget=forget)
                return
            if item.cart_state == 'queued':
                run_pending_cart(pid, page)
            # Keeps Playwright's event dispatch and the CDP connection running.
            page.wait_for_timeout(1000)
        finish(provider, pid)


def run_pending_cart(pid, page):
    from flask import current_app
    from .shop_cart_agent import run_cart
    item = db.session.get(ShopBrowser, pid)
    if item.shop_key == 'coop' and not item.cart_plan_id:
        set_fields(pid, cart_state='UNSUPPORTED_SHOP')
        return
    shop, plan_id = item.shop_key, item.cart_plan_id
    claimed = db.session.execute(update(ShopBrowser).where(
        ShopBrowser.id == pid, ShopBrowser.state == 'active',
        ShopBrowser.cart_state == 'queued').values(cart_state='running',
            version=ShopBrowser.version + 1)).rowcount
    db.session.commit()
    if not claimed:
        return
    deadline = monotonic() + 540

    def stopped():
        db.session.expire_all()
        item = db.session.get(ShopBrowser, pid)
        stop = (not item or item.state != 'active' or not valid(item)
                or item.expires_at <= utcnow() or monotonic() >= deadline)
        if shop == 'coop' and not stop:
            from .planning import coop_preview
            plan = db.session.get(PurchasePlan, plan_id)
            stop = (not plan or plan.household_id != item.household_id or plan.cart_state != 'running'
                    or item.cart_plan_id != plan_id or not coop_preview(plan)['ready'])
        db.session.rollback()
        return stop

    def progress(count):
        set_fields(pid, cart_actions=count)
        if shop == 'coop':
            db.session.execute(update(PurchasePlan).where(PurchasePlan.id == plan_id)
                .values(cart_actions=count, version=PurchasePlan.version+1))
            db.session.commit()

    if shop == 'coop':
        from .planning import coop_preview
        from .coop_cart_agent import run_coop_cart
        plan = db.session.get(PurchasePlan, plan_id)
        preview = coop_preview(plan) if plan and plan.household_id == item.household_id else {'ready':False}
        db.session.rollback()
        result = (run_coop_cart(page, current_app.config.get('OPENAI_API_KEY'), preview['targets'], stopped, progress)
                  if preview['ready'] and not stopped() else 'PLAN_INVALID')
    else:
        result = run_cart(page, current_app.config.get('OPENAI_API_KEY'), stopped, progress)
    set_fields(pid, cart_state=result)
    if shop == 'coop':
        db.session.execute(update(PurchasePlan).where(PurchasePlan.id == plan_id)
            .values(cart_state=result, version=PurchasePlan.version+1))
        db.session.commit()
    current_app.logger.warning('Shopbrowser cart result: %s', result)


def schedule_coop_plan():
    """A durable plan survives browser cleanup; a claimed test never requeues."""
    from .planning import coop_preview
    ids = db.session.scalars(select(PurchasePlan.id).where(PurchasePlan.cart_state == 'queued').order_by(PurchasePlan.id)).all()
    db.session.rollback()
    for plan_id in ids:
        plan = db.session.get(PurchasePlan, plan_id)
        db.session.execute(select(Household.id).where(Household.id == plan.household_id).with_for_update())
        db.session.refresh(plan)
        if plan.cart_state != 'queued':
            db.session.rollback()
            continue
        if not plan.cart_requested_at or plan.cart_requested_at + timedelta(minutes=12) <= utcnow():
            plan.cart_state = 'EXPIRED'
            db.session.commit()
            continue
        profile = db.session.scalar(select(ShopBrowser).where(ShopBrowser.household_id == plan.household_id,
            ShopBrowser.shop_key == 'coop'))
        if not profile or not valid(profile) or not profile.context_id or not coop_preview(plan)['ready']:
            plan.cart_state = 'PLAN_INVALID'
            db.session.commit()
            continue
        busy = db.session.scalar(select(ShopBrowser.id).where(ShopBrowser.household_id == plan.household_id,
            ShopBrowser.state != 'idle'))
        legacy = db.session.scalar(select(ShopLogin.id).where(ShopLogin.active_household_id == plan.household_id))
        if busy or legacy:
            db.session.rollback()
            continue
        plan.cart_state = 'running'
        profile.cart_plan_id = plan.id
        profile.cart_state = 'queued'
        profile.cart_actions = 0
        profile.state = 'queued'
        profile.expires_at = plan.cart_requested_at + timedelta(minutes=12)
        profile.error_category = None
        db.session.commit()


def worker_once(app):
    if not app.config.get('SHOP_BROWSER_ENABLED'):
        return False
    schedule_coop_plan()
    provider = Browserbase(app.config.get('BROWSERBASE_API_KEY'), app.config.get('BROWSERBASE_PROJECT_ID'))
    ids = db.session.scalars(select(ShopBrowser.id)).all()
    db.session.rollback()
    for pid in ids:
        item = db.session.get(ShopBrowser, pid)
        state = item.state
        if state == 'idle' and (valid(item) or (not item.context_id and not item.session_id)):
            db.session.rollback()
            continue
        if state == 'error' and item.error_category == 'creation_unknown':
            db.session.rollback()
            continue
        app.logger.warning('Shopbrowser pending: state=%s session=%s context=%s',
                           state, bool(item.session_id), bool(item.context_id))
        try:
            if state == 'queued' and valid(item) and item.expires_at > utcnow():
                claimed = db.session.execute(update(ShopBrowser).where(ShopBrowser.id == pid,
                    ShopBrowser.state == 'queued').values(state='creating', version=ShopBrowser.version + 1)).rowcount
                db.session.commit()
                if claimed:
                    connect(provider, pid)
                    return True
            elif state == 'creating' and not item.session_id:
                set_fields(pid, state='error', live_url=None, error_category='creation_unknown')
                if item.cart_plan_id:
                    set_fields(pid, cart_state='CREATION_UNKNOWN')
                    db.session.execute(update(PurchasePlan).where(PurchasePlan.id == item.cart_plan_id,
                        PurchasePlan.cart_state == 'running').values(cart_state='CREATION_UNKNOWN',version=PurchasePlan.version+1))
                    db.session.commit()
            else:
                forget = state == 'forgetting' or not valid(item)
                db.session.rollback()
                finish(provider, pid, forget=forget)
        except Exception as exc:
            db.session.rollback()
            item = db.session.get(ShopBrowser, pid)
            rejected = isinstance(exc, BrowserUnavailable) and exc.status in (400, 401, 402, 403, 404, 422, 429) and not item.session_id
            unknown = item.state == 'creating' and not item.session_id and not rejected
            forgetting = item.state == 'forgetting'
            # Fixed categories only: never log provider URLs, credentials or error bodies.
            app.logger.warning('Shopbrowser operation failed: state=%s http=%s kind=%s',
                               item.state, exc.status if isinstance(exc, BrowserUnavailable) else 0,
                               'provider' if isinstance(exc, BrowserUnavailable) else 'internal')
            set_fields(pid, state='forgetting' if forgetting else 'idle' if rejected else 'error', live_url=None,
                       error_category=('provider_http_' + str(exc.status)) if rejected else 'creation_unknown' if unknown else 'cleanup_pending' if item.session_id else 'browser_unavailable')
            if item.cart_plan_id:
                result = ('PROVIDER_HTTP_' + str(exc.status)) if rejected else 'CREATION_UNKNOWN' if unknown else 'INTERRUPTED'
                set_fields(pid, cart_state=result)
                db.session.execute(update(PurchasePlan).where(PurchasePlan.id == item.cart_plan_id,
                    PurchasePlan.cart_state == 'running').values(cart_state=result,version=PurchasePlan.version+1))
                db.session.commit()
        finally:
            db.session.remove()
    return False
