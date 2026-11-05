"""Shared household rules. Routes own commit/rollback, services never commit."""
import re
import secrets
from datetime import timedelta
from hashlib import sha256
from uuid import UUID

from flask import abort
from sqlalchemy import select

from .extensions import db
from .models import Activity, Household, HouseholdItem, Invitation, Membership, ShoppingNeed, User, utcnow


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
        raise ValueError("Bitte eine gültige E-Mail-Adresse eingeben.")
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
    # Serialize issuance even when there is no existing invitation row to lock.
    db.session.scalar(select(Household).where(
        Household.id == membership.household_id).with_for_update())
    if db.session.scalar(select(User.id).where(User.email == email)):
        raise ValueError("Für diese Adresse besteht bereits ein Zugang.")
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
        raise ValueError("Diese Einladung ist ungültig oder abgelaufen.")
    invitation = db.session.scalar(select(Invitation).where(
        Invitation.token_hash == sha256(token.encode()).hexdigest()).with_for_update())
    now = utcnow()
    if not invitation or invitation.consumed_at or invitation.revoked_at or invitation.expires_at <= now:
        raise ValueError("Diese Einladung ist ungültig oder abgelaufen.")
    issuer = membership_for(invitation.created_by)
    if not issuer or issuer.role != "owner" or issuer.household_id != invitation.household_id:
        raise ValueError("Diese Einladung ist nicht mehr gültig.")
    email = clean_email(email)
    if email != invitation.email:
        raise ValueError("Die E-Mail-Adresse passt nicht zu dieser Einladung.")
    name = clean_text(name, "Name", 80)
    validate_password(password)
    if db.session.scalar(select(User.id).where(User.email == email)):
        raise ValueError("Für diese Adresse besteht bereits ein Zugang. Bitte anmelden.")
    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    db.session.add(Membership(user_id=user.id, household_id=invitation.household_id))
    invitation.consumed_at = now
    return user


def item_values(data):
    return dict(name=clean_text(data.get("name"), "Artikelname", 100),
        category=clean_text(data.get("category") or "Sonstiges", "Warengruppe", 60),
        source=clean_text(data.get("source") or "Laden", "Bezugsquelle", 60),
        unit=clean_text(data.get("unit") or "Packung", "Einheit", 20),
        default_quantity=positive_int(data.get("quantity", "1")))


def valid_status(value):
    if value not in {"unknown", "available", "low", "empty"}:
        raise ValueError("Bitte einen gültigen Bestandsstatus wählen.")
    return value


def item_state(item, need):
    from .assortment import source_ids
    return {"status": item.stock_status, "quantity": need.quantity,
        "name": item.name, "category": item.category, "source": item.source,
        "unit": item.unit, "default_quantity": item.default_quantity,
        "is_favorite": item.is_favorite, "archived": item.archived, "source_ids": source_ids(item), "recipe_context": need.recipe_context or []}


def create_item(household_id, data):
    from .assortment import canonical_labels, lock_household, sync_sources
    lock_household(household_id)
    values = item_values(data)
    values["category"], values["source"] = canonical_labels(household_id, values["category"], values["source"])
    item = HouseholdItem(household_id=household_id, **values,
        is_favorite=data.get("favorite") == "1",
        stock_status=valid_status(data.get("stock_status", "unknown")))
    db.session.add(item)
    db.session.flush()
    db.session.add(ShoppingNeed(item_id=item.id, quantity=0))
    sync_sources(item, data)
    db.session.flush()
    return item


def change_item(household_id, user_id, item_id, action, request_id, expected_version, quantity=None, activity_id=None, data=None):
    # Catalogue/link lookups must not flush metadata halfway through a versioned action.
    with db.session.no_autoflush:
        return _change_item(household_id, user_id, item_id, action, request_id, expected_version,
            quantity, activity_id, data)


def _change_item(household_id, user_id, item_id, action, request_id, expected_version, quantity=None, activity_id=None, data=None):
    from .assortment import canonical_labels, lock_household, sync_sources
    try:
        request_id = str(UUID(str(request_id)))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Ungültige Anfrage. Bitte die Seite neu laden.") from None
    lock_household(household_id)
    item = db.session.scalar(select(HouseholdItem).where(
        HouseholdItem.id == item_id, HouseholdItem.household_id == household_id).with_for_update())
    if not item:
        abort(404)
    existing = db.session.scalar(select(Activity).where(
        Activity.household_id == household_id, Activity.request_id == request_id))
    if existing:
        if existing.item_id != item_id or existing.action != action:
            raise Conflict("Diese Anfrage wurde bereits für eine andere Aktion verwendet.")
        return existing
    try:
        valid_version = int(expected_version) == item.version
    except (TypeError, ValueError):
        valid_version = False
    if not valid_version:
        raise Conflict("Der Artikel wurde inzwischen geändert. Bitte neu laden und erneut prüfen.")
    need = db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == item.id))
    if item.archived and action not in {"restore", "undo"}:
        raise Conflict("Dieser Artikel ist archiviert. Bitte zuerst wieder aktivieren.")
    before = item_state(item, need)
    data = data or {}
    undo_target = None
    if action in {"replenish", "empty"}:
        if need.quantity == 0:
            need.quantity = item.default_quantity
        item.stock_status = "empty" if action == "empty" else ("empty" if item.stock_status == "empty" else "low")
    elif action == "recipe_need":
        origin = data.get('recipe_origin')
        if not isinstance(origin, dict) or not isinstance(origin.get('recipe_id'), int):
            raise ValueError('Ungültige Rezeptzuordnung.')
        if not need.quantity:
            need.quantity = item.default_quantity
        contexts = list(need.recipe_context or [])
        contexts = [entry for entry in contexts if entry.get('recipe_id') != origin['recipe_id']]
        need.recipe_context = [*contexts, origin][-30:]
    elif action == "extra":
        amount = positive_int(quantity)
        if need.quantity + amount > 999:
            raise ValueError("Die offene Menge darf höchstens 999 betragen.")
        need.quantity += amount
    elif action == "purchase":
        amount = positive_int(quantity)
        if amount > need.quantity:
            raise Conflict("Die Einkaufsmenge ist grösser als der offene Bedarf. Bitte die Liste neu laden.")
        need.quantity -= amount
        item.stock_status = "available"
    elif action == "receipt":
        amount = positive_int(quantity)
        need.quantity = max(0, need.quantity - amount)
        item.stock_status = "available"
    elif action == "remove":
        need.quantity = 0
    elif action == "status":
        item.stock_status = valid_status(data.get("stock_status"))
    elif action == "favorite":
        if data.get("favorite") not in {"0", "1"}:
            raise ValueError("Bitte einen gültigen Favoritenstatus wählen.")
        item.is_favorite = data["favorite"] == "1"
    elif action == "edit":
        values = item_values(data)
        values["category"], values["source"] = canonical_labels(household_id, values["category"], values["source"])
        if need.quantity and values["unit"] != item.unit:
            raise Conflict("Die Einheit kann bei offenem Einkaufsbedarf nicht geändert werden. Bitte zuerst die Position von der Liste entfernen.")
        if values["unit"] != item.unit:
            from .assortment import offer_source_ids
            if offer_source_ids(item):
                raise Conflict("Aktive Produktzuordnungen verwenden diese Einheit. Bitte zuerst die Shop-Zuordnungen deaktivieren und danach die Packungsmengen neu prüfen.")
        for field, value in values.items():
            setattr(item, field, value)
        item.stock_status = valid_status(data.get("stock_status"))
        item.is_favorite = data.get("favorite") == "1"
        sync_sources(item, data)
    elif action == "archive":
        if need.quantity:
            raise Conflict("Der Artikel steht noch auf der Einkaufsliste. Bitte zuerst den offenen Bedarf erledigen oder von der Liste entfernen.")
        item.archived = True
    elif action == "restore":
        item.archived = False
    elif action == "undo":
        undo_target = db.session.scalar(select(Activity).where(
            Activity.id == activity_id, Activity.household_id == household_id,
            Activity.item_id == item.id).with_for_update())
        if not undo_target or undo_target.action == "undo" or undo_target.reversed_by_id or undo_target.version_after != item.version:
            raise Conflict("Rückgängig ist nach einer weiteren Änderung nicht mehr möglich.")
        if undo_target.before_state.get("unit", item.unit) != item.unit:
            from .assortment import offer_source_ids
            if offer_source_ids(item):
                raise Conflict("Aktive Produktzuordnungen verwenden die aktuelle Einheit. Bitte zuerst die Shop-Zuordnungen deaktivieren.")
        need.recipe_context = undo_target.before_state.get("recipe_context", [])
        item.stock_status = undo_target.before_state["status"]
        need.quantity = undo_target.before_state["quantity"]
        # Existing activities may predate metadata snapshots.
        for field in ("name", "category", "source", "unit", "default_quantity", "is_favorite", "archived"):
            if field in undo_target.before_state:
                setattr(item, field, undo_target.before_state[field])
        item.category, item.source = canonical_labels(household_id, item.category, item.source, allow_inactive=True)
        restored_sources = undo_target.before_state.get("source_ids")
        if restored_sources is None and "source" in undo_target.before_state:
            restored_sources = []
        sync_sources(item, restore_ids=restored_sources)
    else:
        raise ValueError("Unbekannte Aktion.")
    if need.quantity == 0:
        need.recipe_context = []
    from .planning import clamp_reservations
    clamp_reservations(item, need)
    # Version advances even when only ShoppingNeed changed, or the action was a no-op.
    item.version += 1
    db.session.flush()
    event = Activity(household_id=household_id, user_id=user_id, item_id=item.id,
        request_id=request_id, action=action, before_state=before,
        after_state=item_state(item, need), version_after=item.version)
    db.session.add(event)
    db.session.flush()
    if undo_target:
        undo_target.reversed_by_id = event.id
    return event
