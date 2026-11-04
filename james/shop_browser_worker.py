"""Single-replica worker holding CDP open during the user's manual login."""
from time import monotonic, sleep

from sqlalchemy import select, update

from .extensions import db
from .models import ShopBrowser, User, utcnow
from .services import membership_for
from scripts.shop_browser_context import Browserbase, BrowserUnavailable, identifier


def valid(item):
    user = db.session.get(User, item.user_id, populate_existing=True)
    member = membership_for(item.user_id)
    return bool(user and user.active and user.auth_version == item.auth_version and member
                and member.role == 'owner' and member.household_id == item.household_id)


def set_fields(pid, **values):
    # UI version checks must also detect worker state transitions.
    db.session.execute(update(ShopBrowser).where(ShopBrowser.id == pid)
                       .values(**values, version=ShopBrowser.version + 1))
    db.session.commit()


def finish(provider, pid, *, forget=False, pause=sleep):
    db.session.expire_all()
    item = db.session.get(ShopBrowser, pid)
    sid, context = item.session_id, item.context_id
    db.session.rollback()
    if sid:
        status = provider.session(sid)['status']
        if status not in ('COMPLETED', 'TIMED_OUT', 'ERROR'):
            provider.release(sid)
        for _ in range(10):
            if provider.session(sid)['status'] in ('COMPLETED', 'TIMED_OUT', 'ERROR'):
                break
            pause(1)
        else:
            raise BrowserUnavailable('cleanup_pending')
        pause(5)
    # Read the latest request; a forget request must not be lost during release.
    db.session.expire_all()
    item = db.session.get(ShopBrowser, pid)
    forget = forget or item.state == 'forgetting' or not valid(item)
    db.session.rollback()
    if forget and context:
        try:
            provider.delete_context(context)
        except BrowserUnavailable as exc:
            if 'HTTP 404' not in str(exc):
                raise
    set_fields(pid, session_id=None, live_url=None, state='idle', error_category=None,
               **({'context_id': None, 'confirmed_at': None} if forget else {}))


def connect(provider, pid):
    # Claimed queued job is never automatically retried after a crash.
    item = db.session.get(ShopBrowser, pid)
    context = item.context_id
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
        page.goto('https://www.galaxus.ch/', wait_until='domcontentloaded', timeout=30000)
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
            # Keeps Playwright's event dispatch and the CDP connection running.
            page.wait_for_timeout(1000)
        finish(provider, pid)


def worker_once(app):
    if not app.config.get('SHOP_BROWSER_ENABLED'):
        return False
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
            set_fields(pid, state='forgetting' if forgetting else 'idle' if rejected else 'error', live_url=None,
                       error_category=('provider_http_' + str(exc.status)) if rejected else 'creation_unknown' if unknown else 'cleanup_pending' if item.session_id else 'browser_unavailable')
        finally:
            db.session.remove()
    return False
