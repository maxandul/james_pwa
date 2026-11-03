from decimal import Decimal

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select

from .assortment import (CATEGORIES, SOURCES, entries, item_offers, item_products, key,
    save_entry, save_offer, save_product)
from .extensions import db
from .models import HouseholdItem, Product, Household
from .services import Conflict
from .views import household_required

products = Blueprint("products", __name__)


@products.app_template_filter("amount")
def amount(value):
    return format(Decimal(value).normalize(), "f").replace(".", ",")


@products.app_context_processor
def catalogue_choices():
    if not getattr(g, "household", None):
        return {}
    categories, sources = entries(g.household.id, "category"), entries(g.household.id, "source")
    catalogues = {"category": categories, "source": sources}
    def label(kind, name):
        name_key = key(str(name or ""))
        entry = next((entry for entry in catalogues[kind]
            if entry.name_key == name_key or name_key in entry.aliases), None)
        return entry.name if entry else str(name or "")
    home = g.household
    def choices(kind, defaults, records):
        all_records = entries(home.id, kind, include_inactive=True)
        blocked = {value for value in home.settings.get('catalogue_deleted', [])}
        blocked |= {f'{kind}:{name}' for entry in all_records if not entry.active for name in (entry.name_key, *entry.aliases)}
        return sorted({label(kind, name) for name in defaults if f'{kind}:{key(name)}' not in blocked} | {entry.name for entry in records})
    return {"category_names": choices('category', CATEGORIES, categories),
        "source_names": choices('source', SOURCES, sources),
        "purchase_sources": sources, "catalogue_label": label}


@products.route("/catalogue", methods=["GET", "POST"])
@household_required
def catalogue():
    if g.membership.role != 'owner':
        abort(403)
    if request.method == 'GET':
        return redirect(url_for('settings.catalogue', kind='category'))
    error, status = None, 200
    if request.method == "POST":
        try:
            from .administration import locked_membership
            locked_membership()
            raw_id = request.form.get("entry_id")
            try:
                entry_id = int(raw_id) if raw_id else None
            except ValueError:
                raise ValueError("Bitte die Liste neu laden.") from None
            save_entry(g.household.id, request.form.get("kind"), request.form.get("name"),
                entry_id, request.form.get("version"))
            db.session.commit()
            flash("Bezeichnung gespeichert. Zugeordnete Artikel bleiben erhalten.", "success")
            return redirect(url_for("products.catalogue"))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), 409 if isinstance(exc, Conflict) else 400
    return render_template("catalogue.html", categories=entries(g.household.id, "category"),
        sources=entries(g.household.id, "source"), error=error), status


def scoped_item(item_id):
    item = db.session.scalar(select(HouseholdItem).where(
        HouseholdItem.id == item_id, HouseholdItem.household_id == g.household.id))
    if not item:
        abort(404)
    return item


@products.route("/items/<int:item_id>/products", methods=["GET", "POST"])
@products.route("/items/<int:item_id>/products/<int:product_id>", methods=["GET", "POST"])
@household_required
def manage(item_id, product_id=None):
    item = scoped_item(item_id)
    editing = db.session.scalar(select(Product).where(Product.id == product_id,
        Product.item_id == item_id, Product.household_id == g.household.id)) if product_id else None
    if product_id and not editing:
        abort(404)
    error, status = None, 200
    if request.method == "POST":
        try:
            save_product(g.household.id, item_id, request.form, product_id)
            db.session.commit()
            flash("Produkt gespeichert. Bestand und Einkaufsliste bleiben unveraendert.", "success")
            return redirect(url_for("products.manage", item_id=item_id))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), 409 if isinstance(exc, Conflict) else 400
    return render_template("products.html", item=item, variants=item_products(item),
        offers=item_offers(item), editing=editing, error=error), status


@products.post("/items/<int:item_id>/products/<int:product_id>/offers")
@products.post("/items/<int:item_id>/products/<int:product_id>/offers/<int:offer_id>")
@household_required
def offer(item_id, product_id, offer_id=None):
    item = scoped_item(item_id)
    try:
        save_offer(g.household.id, item_id, product_id, request.form, offer_id,
            expected_unit=request.form.get("item_unit", ""))
        db.session.commit()
        flash("Shop-Zuordnung gespeichert. Es wurde nichts bestellt.", "success")
        return redirect(url_for("products.manage", item_id=item_id))
    except ValueError as exc:
        db.session.rollback()
        return render_template("products.html", item=item, variants=item_products(item),
            offers=item_offers(item), editing=None, error=str(exc), offer_values=request.form, failed_product_id=product_id, failed_offer_id=offer_id), 409 if isinstance(exc, Conflict) else 400
