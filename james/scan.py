from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select

from .barcodes import find_barcode, normalize_barcode, register_barcode, remove_barcode
from .catalog import CatalogUnavailable, cached_suggestion, fetch_suggestion, reserve_catalog_lookup, save_suggestion
from .extensions import db
from .models import HouseholdItem
from .services import Conflict
from .views import household_required

scan = Blueprint("scan", __name__)


def load_flow():
    """Only named local destinations; article targets are always household-scoped."""
    values = request.form if request.method == "POST" else request.args
    flow = values.get("flow", "replenish")
    if flow not in {"create", "assign", "replenish"}:
        flow = "replenish"
    target = None
    if flow == "assign":
        item_id = values.get("context_item_id", type=int)
        target = db.session.scalar(select(HouseholdItem).where(
            HouseholdItem.id == item_id, HouseholdItem.household_id == g.household.id))
        if not target:
            abort(404)
    back = url_for("main.item_edit", item_id=target.id) if target else url_for(
        "main.item_new" if flow == "create" else "main.home")
    titles = {"create": "Artikel per Barcode erfassen", "assign": "Barcode zuordnen", "replenish": "Nachkaufen per Barcode"}
    descriptions = {
        "create": "Produkt scannen oder Nummer eingeben. Danach die Artikelangaben prüfen und speichern.",
        "assign": f"Ein Produkt für {target.name} scannen oder seine Nummer eingeben." if target else "",
        "replenish": "Artikel per Barcode finden. Danach Nachkaufen oder Leer und nachkaufen wählen.",
    }
    g.scan_context = {"scan_flow": flow, "target_item": target, "scan_back": back,
        "scan_title": titles[flow], "scan_description": descriptions[flow],
        "scan_again": url_for("scan.index", flow=flow, context_item_id=target.id if target else None)}


@scan.context_processor
def flow_context():
    return getattr(g, "scan_context", {})


def found_page(barcode):
    target = g.scan_context["target_item"]
    if target and barcode.product.item_id != target.id:
        return render_template("scan_found.html", barcode=barcode, item=barcode.product.item,
            assignment_conflict=True), 409
    if target:
        flash("Dieser Barcode ist diesem Artikel bereits zugeordnet.", "success")
        return redirect(g.scan_context["scan_back"])
    return render_template("scan_found.html", barcode=barcode, item=barcode.product.item)


def registration_page(code, values=None, error=None, catalog_message=None, catalog_source=False, status=200):
    items = db.session.scalars(select(HouseholdItem).where(
        HouseholdItem.household_id == g.household.id, HouseholdItem.archived.is_(False)).order_by(HouseholdItem.name)).all()
    return render_template("barcode_register.html", code=code, items=items, values=values or {}, error=error,
        catalog_message=catalog_message, catalog_source=catalog_source,
        catalog_staging=current_app.config["OPENFOODFACTS_ENVIRONMENT"] == "staging"), status


@scan.route("/scan", methods=["GET", "POST"])
@household_required
def index():
    load_flow()
    if request.method == "GET":
        return render_template("scan.html")
    try:
        code, gtin = normalize_barcode(request.form.get("code", ""))
    except ValueError as exc:
        return render_template("scan.html", error=str(exc), code=request.form.get("code", "")[:64]), 400
    known = find_barcode(g.household.id, code)
    if known:
        return found_page(known)
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
                message = "Produktvorschlag gefunden. Bitte Name, Marke und Packungsangabe prüfen."
            else:
                message = "Kein Produktvorschlag gefunden. Du kannst die Angaben selbst ergänzen."
        except CatalogUnavailable as exc:
            db.session.rollback()
            message = str(exc)
    return registration_page(code, values, catalog_message=message, catalog_source=source)


@scan.post("/barcodes")
@household_required
def register():
    load_flow()
    try:
        code, gtin = normalize_barcode(request.form.get("code", ""))
        values = request.form.to_dict()
        target = g.scan_context["target_item"]
        if target:
            values["item_id"] = str(target.id)
        barcode, created = register_barcode(g.household.id, values)
        db.session.commit()
        flash("Barcode gespeichert." if created else "Dieser Barcode ist bereits bekannt. Die Zuordnung bleibt unverändert.", "success")
        if g.scan_context["scan_flow"] in {"create", "assign"}:
            return redirect(url_for("main.item_edit", item_id=barcode.product.item_id))
        return found_page(barcode)
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
