from functools import wraps
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select, text

from .extensions import db
from .models import Activity, HouseholdItem, Invitation, Membership, ShoppingNeed, utcnow
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


@main.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        db.session.rollback()
        return {"status": "unavailable"}, 503


@main.get("/")
@household_required
def home():
    rows = db.session.execute(select(HouseholdItem, ShoppingNeed).join(ShoppingNeed).where(
        HouseholdItem.household_id == g.household.id).order_by(HouseholdItem.name)).all()
    pending = sum(1 for item, need in rows if need.quantity)
    return render_template("home.html", rows=rows, pending=pending)


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


@main.get("/shopping")
@household_required
def shopping():
    rows = db.session.execute(select(HouseholdItem, ShoppingNeed).join(ShoppingNeed).where(
        HouseholdItem.household_id == g.household.id, ShoppingNeed.quantity > 0
    ).order_by(HouseholdItem.category, HouseholdItem.name)).all()
    sources = sorted({item.source for item, need in rows})
    source = request.args.get("source", "")
    if source:
        rows = [(item, need) for item, need in rows if item.source == source]
    return render_template("shopping.html", rows=rows, sources=sources, selected_source=source)


@main.post("/items/<int:item_id>/action")
@household_required
def item_action(item_id):
    try:
        event = change_item(g.household.id, current_user.id, item_id,
            request.form.get("action"), request.form.get("request_id"),
            request.form.get("version"), request.form.get("quantity"))
        db.session.commit()
        session_event = event.id
        flash("Einkauf gespeichert." if event.action == "purchase" else "Einkaufsliste aktualisiert.", "success")
        # Reference only; no state mutation on the destination GET.
        destination = "main.shopping" if request.form.get("return_to") == "shopping" else "main.home"
        return redirect(url_for(destination, undo=session_event))
    except ValueError as exc:
        db.session.rollback()
        return render_template("error.html", message=str(exc)), (409 if isinstance(exc, Conflict) else 400)


@main.app_context_processor
def undo_context():
    event = None
    label = None
    if getattr(g, "household", None) and request.endpoint in {"main.home", "main.shopping"}:
        # Persistent across navigation, but never offer an older action in place
        # of a latest action that was undone or superseded by another member.
        latest = db.session.scalar(select(Activity).where(
            Activity.household_id == g.household.id,
            Activity.user_id == current_user.id).order_by(Activity.id.desc()).limit(1))
        if latest and latest.action != "undo" and not latest.reversed_by_id and latest.version_after == latest.item.version:
            event = latest
            labels = {"replenish": "Zum Nachkaufen vorgemerkt", "empty": "Als leer markiert",
                "extra": "Zusätzliche Menge erfasst", "purchase": "Als gekauft markiert"}
            label = labels.get(event.action, "Einkaufsliste aktualisiert")
    return {"undo_event": event, "undo_label": label}


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
        flash("Aenderung rueckgaengig gemacht.", "success")
        return redirect(url_for("main.shopping"))
    except ValueError as exc:
        db.session.rollback()
        return render_template("error.html", message=str(exc)), 409


@main.route("/household", methods=["GET", "POST"])
@household_required
def household():
    if g.membership.role != "owner":
        abort(403)
    error = None
    if request.method == "POST":
        try:
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
    invitation = db.session.scalar(select(Invitation).where(
        Invitation.id == invitation_id, Invitation.household_id == g.household.id).with_for_update())
    if not invitation:
        abort(404)
    invitation.revoked_at = utcnow()
    db.session.commit()
    flash("Einladung widerrufen.", "success")
    return redirect(url_for("main.household"))
