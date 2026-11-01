"""Public offline shell and a private, read-only shopping snapshot."""
from flask import Blueprint, g, jsonify, make_response, send_from_directory
from flask_login import current_user
from sqlalchemy import select

from .extensions import db
from .models import HouseholdItem, ShoppingNeed, utcnow
from .services import membership_for

pwa = Blueprint("pwa", __name__)


def owner_key(membership):
    return f"{current_user.id}:{current_user.auth_version}:{membership.household_id}"


@pwa.app_context_processor
def offline_identity():
    membership = getattr(g, "membership", None)
    return {"offline_owner": owner_key(membership) if current_user.is_authenticated and membership else ""}


@pwa.get("/manifest.webmanifest")
def manifest():
    return send_from_directory("static", "manifest.webmanifest", mimetype="application/manifest+json")


@pwa.get("/sw.js")
def service_worker():
    response = send_from_directory("static", "sw.js", mimetype="text/javascript")
    response.headers["Cache-Control"] = "no-cache"
    return response


@pwa.get("/offline")
def offline():
    # This cacheable shell contains no identity, CSRF tokens or household data.
    return send_from_directory("static", "offline.html", mimetype="text/html")


@pwa.get("/api/offline-list")
def shopping_snapshot():
    response = None
    if not current_user.is_authenticated:
        response = jsonify(error="login_required"), 401
    else:
        membership = membership_for(current_user.id)
        if not membership:
            response = jsonify(error="membership_required"), 403
        else:
            captured_at = utcnow().isoformat(timespec="microseconds") + "Z"
            rows = db.session.execute(select(HouseholdItem, ShoppingNeed).join(ShoppingNeed).where(
                HouseholdItem.household_id == membership.household_id,
                HouseholdItem.archived.is_(False), ShoppingNeed.quantity > 0
            ).order_by(HouseholdItem.category, HouseholdItem.name)).all()
            response = jsonify(owner=owner_key(membership), household=membership.household.name,
                saved_at=captured_at, items=[{
                    "name": item.name, "category": item.category, "source": item.source,
                    "quantity": need.quantity, "unit": item.unit,
                } for item, need in rows])
    result = make_response(response)
    result.headers["Cache-Control"] = "no-store"
    return result
