from functools import wraps
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from .extensions import db
from .models import Activity, HouseholdItem, Invitation, Membership, Product, ProductBarcode, ShoppingNeed, utcnow
from .readiness import database_ready
from .services import Conflict, change_item, create_item, make_invitation, membership_for

main = Blueprint("main", __name__)
STOCK_LABELS = {"unknown": "Bestand unbekannt", "available": "Vorhanden", "low": "Wird knapp", "empty": "Leer"}


def household_required(function):
    @wraps(function)
    @login_required
    def wrapped(*args, **kwargs):
        g.membership = membership_for(current_user.id)
        if not g.membership:
            abort(403)
        g.household = g.membership.household
        return function(*args, **kwargs)
    return wrapped


@main.app_context_processor
def helpers():
    return {"request_id": lambda: str(uuid4()), "stock_labels": STOCK_LABELS}


def list_filters(destination, values):
    """Explicit local list context, shared by actions, undo and detail links."""
    if destination == "main.shopping":
        source = values.get("source", "").strip()[:60]
        result = {"source": source} if source else {}
        try:
            view_id = int(values.get('view_id') or 0)
        except (ValueError, TypeError):
            view_id = 0
        if 'view_id' in values:
            result['view_id'] = max(0, view_id)
        return result
    view = values.get("view", "all")
    layout = getattr(g, 'household', None).settings.get('layout', 'compact') if getattr(g, 'household', None) else 'compact'
    if current_user.is_authenticated and current_user.preferences.get('layout') in {'compact', 'cards'}:
        layout = current_user.preferences['layout']
    result = {"view": view if view in {"all", "favorites", "archived"} else "all",
        "layout": "cards" if values.get("layout", layout) == "cards" else "compact"}
    query = (values.get("q") or "").strip()[:100]
    if query:
        result["q"] = query
    for field in ('filter_category', 'filter_source'):
        value = (values.get(field) or '').strip()[:60]
        if value:
            result[field] = value
    if values.get('filter_stock') in STOCK_LABELS:
        result['filter_stock'] = values['filter_stock']
    try:
        page = max(1, min(int(values.get('page', 1)), 1_000_000))
    except (ValueError, TypeError):
        page = 1
    if page > 1:
        result['page'] = page
    return result


@main.app_context_processor
def list_context():
    values = request.form if request.method == "POST" else request.args
    context = list_filters("main.home", values)
    def home_url(**changes):
        return url_for('main.home', **list_filters('main.home', {**context, **changes}))
    return {"home_context": context, "home_url": home_url}


@main.get("/health")
def health():
    try:
        if database_ready():
            return {"status": "ok"}
        return {"status": "unavailable"}, 503
    except Exception:
        db.session.rollback()
        return {"status": "unavailable"}, 503


@main.get("/")
@household_required
def home():
    from .browsing import browse
    context = list_filters('main.home', request.args)
    result = browse(g.household.id, context)
    if result['page'] != context.get('page', 1):
        context['page'] = result['page']
        return redirect(url_for('main.home', **list_filters('main.home', context),
            undo=request.args.get('undo', type=int)))
    return render_template('home.html', **result, view=context['view'],
        query=context.get('q', ''), layout=context['layout'])


@main.route("/items/new", methods=["GET", "POST"])
@household_required
def item_new():
    error = None
    if request.method == "POST":
        try:
            create_item(g.household.id, request.form)
            db.session.commit()
            flash("Artikel gespeichert. Du kannst ihn jetzt nachkaufen.", "success")
            return redirect(url_for("main.home"))
        except ValueError as exc:
            db.session.rollback()
            error = str(exc)
    return render_template("item_new.html", error=error), (400 if error else 200)


@main.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@household_required
def item_edit(item_id):
    item = db.session.scalar(select(HouseholdItem).where(
        HouseholdItem.id == item_id, HouseholdItem.household_id == g.household.id))
    if not item:
        abort(404)
    error = None
    status = 200
    if request.method == "POST":
        try:
            event = change_item(g.household.id, current_user.id, item_id, "edit",
                request.form.get("request_id"), request.form.get("version"), data=request.form)
            db.session.commit()
            flash("Artikel aktualisiert.", "success")
            return redirect(url_for("main.home", undo=event.id, **list_filters("main.home", request.form)))
        except ValueError as exc:
            db.session.rollback()
            error = str(exc)
            status = 409 if isinstance(exc, Conflict) else 400
    need = db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == item.id))
    barcodes = db.session.scalars(select(ProductBarcode).join(Product).where(
        ProductBarcode.household_id == g.household.id, Product.household_id == g.household.id,
        Product.item_id == item.id).order_by(ProductBarcode.id)).all()
    from .assortment import source_ids, offer_source_ids
    return render_template("item_edit.html", item=item, need=need, error=error, conflict=status == 409,
        barcodes=barcodes, selected_source_ids=source_ids(item), fixed_source_ids=offer_source_ids(item)), status


@main.get("/shopping")
@household_required
def shopping():
    rows = db.session.execute(select(HouseholdItem, ShoppingNeed).join(ShoppingNeed).where(
        HouseholdItem.household_id == g.household.id, HouseholdItem.archived.is_(False), ShoppingNeed.quantity > 0
    ).order_by(HouseholdItem.category, HouseholdItem.name)).all()
    from .assortment import shopping_options, selected_offer
    allowed, offers = shopping_options(rows)
    sources = sorted({name for names in allowed.values() for name in names})
    from .shopping_views import arrange, resolve_view
    selected_view, source, saved_views = resolve_view(request.args)
    if source:
        rows = [(item, need) for item, need in rows if source in allowed[item.id]]
    rows, shopping_groups, hidden_count = arrange(rows, selected_view)
    choices = {item.id: selected_offer(offers[item.id], source, need.quantity) for item, need in rows} if source else {}
    from .planning import reservations
    return render_template("shopping.html", rows=rows, sources=sources, selected_source=source,
        allowed_sources=allowed, choices=choices, planned=reservations(g.household.id),
        selected_view=selected_view, saved_views=saved_views, shopping_groups=shopping_groups, hidden_count=hidden_count)


@main.post("/items/<int:item_id>/action")
@household_required
def item_action(item_id):
    try:
        event = change_item(g.household.id, current_user.id, item_id,
            request.form.get("action"), request.form.get("request_id"),
            request.form.get("version"), request.form.get("quantity"), data=request.form)
        db.session.commit()
        session_event = event.id
        messages = {"purchase": "Einkauf gespeichert.", "remove": "Von der Liste entfernt. Der Bestand bleibt unverändert.",
            "status": "Bestand aktualisiert. Die Einkaufsliste bleibt unverändert.", "favorite": "Favoriten aktualisiert.",
            "archive": "Artikel archiviert.", "restore": "Artikel wieder aktiviert."}
        flash(messages.get(event.action, "Einkaufsliste aktualisiert."), "success")
        # Reference only; no state mutation on the destination GET.
        destination = "main.shopping" if request.form.get("return_to") == "shopping" else "main.home"
        filters = list_filters(destination, request.form)
        if request.form.get("return_to") == "archived" and destination == "main.home":
            filters["view"] = "archived"
        return redirect(url_for(destination, undo=session_event, **filters))
    except ValueError as exc:
        db.session.rollback()
        return render_template("error.html", message=str(exc)), (409 if isinstance(exc, Conflict) else 400)


@main.app_context_processor
def undo_context():
    event = None
    if getattr(g, "household", None):
        activity_id = request.args.get("undo", type=int)
        if activity_id:
            event = db.session.scalar(select(Activity).join(HouseholdItem).where(
                Activity.id == activity_id, Activity.household_id == g.household.id,
                Activity.user_id == current_user.id, Activity.action != "undo",
                Activity.reversed_by_id.is_(None), Activity.version_after == HouseholdItem.version))
    return {"undo_event": event}


@main.post("/activity/<int:activity_id>/undo")
@household_required
def undo(activity_id):
    target = db.session.scalar(select(Activity).where(
        Activity.id == activity_id, Activity.household_id == g.household.id))
    if not target:
        abort(404)
    try:
        change_item(g.household.id, current_user.id, target.item_id, "undo",
            request.form.get("request_id"), request.form.get("version"), activity_id=target.id)
        db.session.commit()
        flash("Änderung rückgängig gemacht.", "success")
        destination = "main.shopping" if request.form.get("return_to") == "shopping" else "main.home"
        return redirect(url_for(destination, **list_filters(destination, request.form)))
    except ValueError as exc:
        db.session.rollback()
        return render_template("error.html", message=str(exc)), 409


@main.route("/household", methods=["GET", "POST"])
@household_required
def household():
    if g.membership.role != "owner":
        abort(403)
    if request.method == 'GET':
        return redirect(url_for('settings.household'))
    error = None
    if request.method == "POST":
        try:
            from .administration import locked_membership
            locked_membership()
            invitation, token = make_invitation(g.membership, request.form.get("email"))
            db.session.commit()
            origin = current_app.config["PUBLIC_BASE_URL"].rstrip("/")
            return render_template("invite_created.html", invitation=invitation, invite_url=f"{origin}/join#{token}")
        except ValueError as exc:
            db.session.rollback()
            error = str(exc)
    members = db.session.scalars(select(Membership).where(Membership.household_id == g.household.id, Membership.active.is_(True))).all()
    invitations = db.session.scalars(select(Invitation).where(
        Invitation.household_id == g.household.id, Invitation.consumed_at.is_(None),
        Invitation.revoked_at.is_(None), Invitation.expires_at > utcnow())).all()
    return render_template("household.html", members=members, invitations=invitations, error=error), (400 if error else 200)


@main.post("/invitations/<int:invitation_id>/revoke")
@household_required
def revoke_invitation(invitation_id):
    if g.membership.role != "owner":
        abort(403)
    from .administration import locked_membership
    locked_membership()
    invitation = db.session.scalar(select(Invitation).where(
        Invitation.id == invitation_id, Invitation.household_id == g.household.id).with_for_update())
    if not invitation:
        abort(404)
    invitation.revoked_at = utcnow()
    db.session.commit()
    flash("Einladung widerrufen.", "success")
    return redirect(url_for("main.household"))
