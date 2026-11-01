from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select

from .barcodes import find_barcode, normalize_barcode, register_barcode, remove_barcode
from .catalog import CatalogUnavailable, cached_suggestion, fetch_suggestion, reserve_catalog_lookup, save_suggestion
from .extensions import db
from .models import HouseholdItem
from .services import Conflict
from .views import household_required

scan = Blueprint("scan", __name__)


def registration_page(code, values=None, error=None, catalog_message=None, catalog_source=False, status=200):
    items = db.session.scalars(select(HouseholdItem).where(
        HouseholdItem.household_id == g.household.id, HouseholdItem.archived.is_(False)).order_by(HouseholdItem.name)).all()
    return render_template("barcode_register.html", code=code, items=items, values=values or {}, error=error,
        catalog_message=catalog_message, catalog_source=catalog_source,
        catalog_staging=current_app.config["OPENFOODFACTS_ENVIRONMENT"] == "staging"), status


@scan.route("/scan", methods=["GET", "POST"])
@household_required
def index():
    if request.method == "GET":
        return render_template("scan.html")
    try:
        code, gtin = normalize_barcode(request.form.get("code", ""))
    except ValueError as exc:
        return render_template("scan.html", error=str(exc), code=request.form.get("code", "")[:64]), 400
    known = find_barcode(g.household.id, code)
    if known:
        return render_template("scan_found.html", barcode=known, item=known.product.item)
    values = request.form.to_dict()
    message = None
    source = False
    if request.form.get("lookup") == "1":
        try:
            cached, suggestion = cached_suggestion(gtin)
            if not cached:
                reserve_catalog_lookup()
                db.session.commit()
                suggestion = fetch_suggestion(code)
                save_suggestion(gtin, suggestion)
                db.session.commit()
            if suggestion:
                for key, value in suggestion.items():
                    if not values.get(key, "").strip():
                        values[key] = value
                source = True
                values["data_source"] = "openfoodfacts_staging" if current_app.config["OPENFOODFACTS_ENVIRONMENT"] == "staging" else "openfoodfacts"
                message = "Produktvorschlag gefunden. Bitte Name, Marke und Packungsangabe pruefen."
            else:
                message = "Kein Produktvorschlag gefunden. Du kannst die Angaben selbst ergaenzen."
        except CatalogUnavailable as exc:
            db.session.rollback()
            message = str(exc)
    return registration_page(code, values, catalog_message=message, catalog_source=source)


@scan.post("/barcodes")
@household_required
def register():
    try:
        code, gtin = normalize_barcode(request.form.get("code", ""))
        barcode, created = register_barcode(g.household.id, request.form)
        db.session.commit()
        flash("Barcode gespeichert. Du kannst den Artikel jetzt nachkaufen." if created else "Dieser Barcode ist bereits bekannt. Die Zuordnung bleibt unveraendert.", "success")
        return render_template("scan_found.html", barcode=barcode, item=barcode.product.item)
    except ValueError as exc:
        db.session.rollback()
        # Invalid input must remain correctable through the scanner form.
        try:
            code, gtin = normalize_barcode(request.form.get("code", ""))
        except ValueError:
            return render_template("scan.html", error=str(exc), code=request.form.get("code", "")[:64]), 400
        return registration_page(code, request.form.to_dict(), error=str(exc), status=409 if isinstance(exc, Conflict) else 400)


@scan.post("/barcodes/<int:barcode_id>/remove")
@household_required
def remove(barcode_id):
    try:
        item_id = remove_barcode(g.household.id, barcode_id, request.form.get("version"))
        db.session.commit()
        flash("Barcode-Zuordnung entfernt. Artikel und Einkaufsbedarf bleiben erhalten.", "success")
        return redirect(url_for("main.item_edit", item_id=item_id))
    except ValueError as exc:
        db.session.rollback()
        return render_template("error.html", message=str(exc)), 409
