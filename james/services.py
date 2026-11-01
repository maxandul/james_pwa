"""Shared household rules. Routes own commit/rollback, services never commit."""
import re
import secrets
from datetime import timedelta
from hashlib import sha256
from uuid import UUID

from flask import abort
from sqlalchemy import select

from .extensions import db
from .models import Activity, HouseholdItem, Invitation, Membership, ShoppingNeed, User, utcnow


class Conflict(ValueError):
    pass


def clean_text(value, label, maximum):
    value = (value or "").strip()
    if not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label}: Bitte 1 bis {maximum} Zeichen eingeben.")
    return value


def clean_email(value):
    value = (value or "").strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Bitte eine gueltige E-Mail-Adresse eingeben.")
    return value


def validate_password(password):
    if not 12 <= len(password) <= 128:
        raise ValueError("Das Passwort braucht 12 bis 128 Zeichen.")


def positive_int(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError("Bitte eine ganze Menge zwischen 1 und 999 eingeben.") from None
    if not 1 <= result <= 999:
        raise ValueError("Bitte eine ganze Menge zwischen 1 und 999 eingeben.")
    return result


def membership_for(user_id):
    return db.session.scalar(select(Membership).where(Membership.user_id == user_id, Membership.active.is_(True)))


def make_invitation(membership, email):
    if membership.role != "owner":
        abort(403)
    email = clean_email(email)
    if db.session.scalar(select(User.id).where(User.email == email)):
        raise ValueError("Fuer diese Adresse besteht bereits ein Zugang.")
    now = utcnow()
    invitations = db.session.scalars(select(Invitation).where(
        Invitation.household_id == membership.household_id,
        Invitation.email == email, Invitation.consumed_at.is_(None), Invitation.revoked_at.is_(None),
    ).with_for_update()).all()
    for invitation in invitations:
        invitation.revoked_at = now
    token = secrets.token_urlsafe(32)
    invitation = Invitation(household_id=membership.household_id, email=email,
        token_hash=sha256(token.encode()).hexdigest(), created_by=membership.user_id,
        expires_at=now + timedelta(days=7))
    db.session.add(invitation)
    return invitation, token


def accept_invitation(token, email, name, password):
    if not isinstance(token, str) or not 32 <= len(token) <= 100:
        raise ValueError("Diese Einladung ist ungueltig oder abgelaufen.")
    invitation = db.session.scalar(select(Invitation).where(
        Invitation.token_hash == sha256(token.encode()).hexdigest()).with_for_update())
    now = utcnow()
    if not invitation or invitation.consumed_at or invitation.revoked_at or invitation.expires_at <= now:
        raise ValueError("Diese Einladung ist ungueltig oder abgelaufen.")
    issuer = membership_for(invitation.created_by)
    if not issuer or issuer.role != "owner" or issuer.household_id != invitation.household_id:
        raise ValueError("Diese Einladung ist nicht mehr gueltig.")
    email = clean_email(email)
    if email != invitation.email:
        raise ValueError("Die E-Mail-Adresse passt nicht zu dieser Einladung.")
    name = clean_text(name, "Name", 80)
    validate_password(password)
    if db.session.scalar(select(User.id).where(User.email == email)):
        raise ValueError("Fuer diese Adresse besteht bereits ein Zugang. Bitte anmelden.")
    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(Membership(user_id=user.id, household_id=invitation.household_id))
    invitation.consumed_at = now
    return user


def create_item(household_id, data):
    item = HouseholdItem(household_id=household_id,
        name=clean_text(data.get("name"), "Artikelname", 100),
        category=clean_text(data.get("category") or "Sonstiges", "Warengruppe", 60),
        source=clean_text(data.get("source") or "Laden", "Bezugsquelle", 60),
        unit=clean_text(data.get("unit") or "Packung", "Einheit", 20),
        default_quantity=positive_int(data.get("quantity", "1")))
    db.session.add(item)
    db.session.flush()
    db.session.add(ShoppingNeed(item_id=item.id, quantity=0))
    return item


def change_item(household_id, user_id, item_id, action, request_id, expected_version, quantity=None, activity_id=None):
    try:
        request_id = str(UUID(str(request_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Ungueltige Anfrage. Bitte die Seite neu laden.") from None
    item = db.session.scalar(select(HouseholdItem).where(
        HouseholdItem.id == item_id, HouseholdItem.household_id == household_id).with_for_update())
    if not item:
        abort(404)
    existing = db.session.scalar(select(Activity).where(
        Activity.household_id == household_id, Activity.request_id == request_id))
    if existing:
        if existing.item_id != item_id or existing.action != action:
            raise Conflict("Diese Anfrage wurde bereits fuer eine andere Aktion verwendet.")
        return existing
    try:
        valid_version = int(expected_version) == item.version
    except (TypeError, ValueError):
        valid_version = False
    if not valid_version:
        raise Conflict("Der Artikel wurde inzwischen geaendert. Bitte neu laden und erneut pruefen.")
    need = db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == item.id))
    before = {"status": item.stock_status, "quantity": need.quantity}
    undo_target = None
    if action in {"replenish", "empty"}:
        if need.quantity == 0:
            need.quantity = item.default_quantity
        item.stock_status = "empty" if action == "empty" else ("empty" if item.stock_status == "empty" else "low")
    elif action == "extra":
        amount = positive_int(quantity)
        if need.quantity + amount > 999:
            raise ValueError("Die offene Menge darf hoechstens 999 betragen.")
        need.quantity += amount
    elif action == "purchase":
        amount = positive_int(quantity)
        if amount > need.quantity:
            raise Conflict("Die Einkaufsmenge ist groesser als der offene Bedarf. Bitte die Liste neu laden.")
        need.quantity -= amount
        item.stock_status = "available"
    elif action == "undo":
        undo_target = db.session.scalar(select(Activity).where(
            Activity.id == activity_id, Activity.household_id == household_id,
            Activity.item_id == item.id).with_for_update())
        if not undo_target or undo_target.action == "undo" or undo_target.reversed_by_id or undo_target.version_after != item.version:
            raise Conflict("Rueckgaengig ist nach einer weiteren Aenderung nicht mehr moeglich.")
        item.stock_status = undo_target.before_state["status"]
        need.quantity = undo_target.before_state["quantity"]
    else:
        raise ValueError("Unbekannte Aktion.")
    # Version advances even when only ShoppingNeed changed, or the action was a no-op.
    item.version += 1
    db.session.flush()
    event = Activity(household_id=household_id, user_id=user_id, item_id=item.id,
        request_id=request_id, action=action, before_state=before,
        after_state={"status": item.stock_status, "quantity": need.quantity}, version_after=item.version)
    db.session.add(event)
    db.session.flush()
    if undo_target:
        undo_target.reversed_by_id = event.id
    return event
