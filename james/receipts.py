"""Reviewed, atomic multi-item purchase import; no direct shop or AI connection."""
from hashlib import sha256
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from flask_login import current_user
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import or_, select

from .assortment import lock_household
from .extensions import db
from .models import Activity, HouseholdItem, Product, ReceiptImport, utcnow
from .receipt_text import clean_receipt_text, extract_text, label_key, parse_lines
from .services import Conflict, change_item, create_item, positive_int
from .views import household_required

receipts = Blueprint("receipts", __name__)


def serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt="receipt-review-v1")


def scoped_receipt(receipt_id):
    receipt = db.session.scalar(select(ReceiptImport).where(ReceiptImport.id == receipt_id,
        ReceiptImport.household_id == g.household.id).execution_options(populate_existing=True))
    if not receipt:
        abort(404)
    return receipt


def create_draft(household_id, text, fingerprint):
    text = clean_receipt_text(text)
    digest = sha256(" ".join(text.split()).encode()).hexdigest()
    lock_household(household_id)
    existing = db.session.scalar(select(ReceiptImport).where(ReceiptImport.household_id == household_id,
        or_(ReceiptImport.fingerprint == fingerprint, ReceiptImport.text_digest == digest)))
    if existing:
        return existing
    receipt = ReceiptImport(household_id=household_id, fingerprint=fingerprint,
        text_digest=digest, text=text, rows=parse_lines(text), activity_ids=[])
    db.session.add(receipt)
    db.session.flush()
    return receipt


def review_items(household_id):
    return db.session.scalars(select(HouseholdItem).where(HouseholdItem.household_id == household_id,
        HouseholdItem.archived.is_(False)).order_by(HouseholdItem.name)).all()


def render_review(receipt, error=None, status=200):
    items = review_items(g.household.id)
    matches = {}
    for item in items:
        matches.setdefault(label_key(item.name), set()).add(item.id)
    for product in db.session.scalars(select(Product).where(Product.household_id == g.household.id)):
        if product.item_id in {item.id for item in items}:
            matches.setdefault(label_key(product.name), set()).add(product.item_id)
    suggestions = {}
    for index, row in enumerate(receipt.rows):
        candidates = matches.get(label_key(row["label"]), set())
        suggestions[index] = str(next(iter(candidates))) if len(candidates) == 1 else ""
    token = serializer().dumps({"receipt": receipt.id, "household": g.household.id,
        "versions": {str(item.id): item.version for item in items}})
    # After a conflict, a new review is required; do not silently replay old quantities.
    return render_template("receipt_review.html", receipt=receipt, items=items,
        suggestions=suggestions, review_token=token, error=error), status


def confirm_receipt(household_id, user_id, receipt_id, data):
    lock_household(household_id)
    receipt = db.session.scalar(select(ReceiptImport).where(ReceiptImport.id == receipt_id,
        ReceiptImport.household_id == household_id).with_for_update().execution_options(populate_existing=True))
    if not receipt:
        abort(404)
    if receipt.state == "confirmed":
        return receipt  # repeated confirmation never books twice
    if receipt.state != "draft":
        raise Conflict("Dieser Beleg wurde rückgängig gemacht und kann nicht erneut verbucht werden.")
    try:
        review = serializer().loads(data.get("review_token", ""), max_age=3600)
        if review["receipt"] != receipt.id or review["household"] != household_id:
            raise BadSignature("scope")
    except (BadSignature, KeyError, TypeError):
        raise Conflict("Die Belegprüfung ist abgelaufen. Bitte neu laden und erneut prüfen.") from None
    grouped, new_items, bookings = {}, {}, {}
    for index, row in enumerate(receipt.rows):
        target = data.get(f"target_{index}", "")
        if not target:
            continue
        quantity = positive_int(data.get(f"quantity_{index}"))
        if target == "new":
            from .services import clean_text
            name = clean_text(data.get(f"name_{index}"), "Artikelname", 100)
            # New rows explicitly use Packung, displayed in the review form.
            key = label_key(name)
            item = new_items.get(key)
            if not item:
                if any(label_key(existing.name) == key for existing in review_items(household_id)):
                    raise Conflict("Dieser Artikel ist bereits vorhanden. Bitte aus der Liste auswählen.")
                item = create_item(household_id, {"name": name, "unit": "Packung", "quantity": "1"})
                new_items[key] = item
            expected = item.version
        else:
            try:
                item_id = int(target)
            except ValueError:
                raise ValueError("Bitte einen gültigen Artikel wählen.") from None
            item = db.session.scalar(select(HouseholdItem).where(HouseholdItem.id == item_id,
                HouseholdItem.household_id == household_id).with_for_update().execution_options(populate_existing=True))
            if not item or item.archived:
                raise Conflict("Ein Artikel ist nicht mehr verfügbar. Bitte die Zuordnung neu prüfen.")
            expected = review.get("versions", {}).get(str(item.id))
            if expected != item.version:
                raise Conflict("Ein Artikel wurde inzwischen geändert. Bitte alle Mengen und Zuordnungen erneut prüfen.")
        previous = grouped.get(item.id, (item, expected, 0))
        total = previous[2] + quantity
        if total > 999:
            raise ValueError("Pro Artikel sind höchstens 999 Einheiten möglich.")
        grouped[item.id] = (item, expected, total)
        bookings[index] = {"item_id": item.id, "name": item.name, "unit": item.unit, "quantity": quantity}
    if not grouped:
        raise ValueError("Bitte mindestens eine Zeile einem Artikel zuordnen.")
    activity_ids = []
    for item, expected, quantity in grouped.values():
        event = change_item(household_id, user_id, item.id, "receipt", str(uuid4()), expected, quantity)
        activity_ids.append(event.id)
    receipt.activity_ids = activity_ids
    receipt.rows = [{**row, "booking": bookings.get(index)} for index, row in enumerate(receipt.rows)]
    receipt.state = "confirmed"
    receipt.confirmed_at = utcnow()
    return receipt


@receipts.route("/receipts/new", methods=["GET", "POST"])
@household_required
def new():
    error = None
    if request.method == "POST":
        try:
            upload = request.files.get("receipt")
            if upload and upload.filename:
                data = upload.read(10 * 1024 * 1024 + 1)
                text = extract_text(data)
                fingerprint = sha256(data).hexdigest()
            else:
                text = clean_receipt_text(request.form.get("text", ""))
                fingerprint = sha256(text.encode()).hexdigest()
            receipt = create_draft(g.household.id, text, fingerprint)
            db.session.commit()
            return redirect(url_for("receipts.review", receipt_id=receipt.id))
        except ValueError as exc:
            db.session.rollback()
            error = str(exc)
    recent = db.session.scalars(select(ReceiptImport).where(ReceiptImport.household_id == g.household.id)
        .order_by(ReceiptImport.id.desc()).limit(10)).all()
    return render_template("receipt_new.html", error=error, recent=recent), 400 if error else 200


@receipts.route("/receipts/<int:receipt_id>", methods=["GET", "POST"])
@household_required
def review(receipt_id):
    receipt = scoped_receipt(receipt_id)
    if request.method == "POST":
        try:
            confirm_receipt(g.household.id, current_user.id, receipt.id, request.form)
            db.session.commit()
            flash("Beleg verbucht. Bestand und offener Bedarf wurden gemeinsam aktualisiert.", "success")
            return redirect(url_for("receipts.review", receipt_id=receipt.id))
        except ValueError as exc:
            db.session.rollback()
            return render_review(scoped_receipt(receipt_id), str(exc), 409 if isinstance(exc, Conflict) else 400)
    return render_review(receipt)


@receipts.post("/receipts/<int:receipt_id>/undo")
@household_required
def undo(receipt_id):
    try:
        lock_household(g.household.id)
        receipt = scoped_receipt(receipt_id)
        if receipt.state != "confirmed":
            raise Conflict("Dieser Beleg ist nicht mehr rückgängig machbar.")
        for event_id in receipt.activity_ids:
            event = db.session.get(Activity, event_id)
            if not event or event.household_id != g.household.id:
                raise Conflict("Die Belegbuchung ist nicht mehr verfügbar.")
            change_item(g.household.id, current_user.id, event.item_id, "undo", str(uuid4()),
                event.version_after, activity_id=event.id)
        receipt.state = "reversed"
        db.session.commit()
        flash("Belegbuchungen rückgängig gemacht. Neu angelegte Artikel bleiben erhalten.", "success")
        return redirect(url_for("receipts.review", receipt_id=receipt_id))
    except ValueError as exc:
        db.session.rollback()
        return render_review(scoped_receipt(receipt_id), str(exc), 409)
