from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select

from .assortment import entries, item_offers, selected_offer
from .extensions import db
from .models import PurchasePlan
from .planning import candidates, change_plan, create_plan, line_description
from .services import Conflict
from .views import household_required

plans = Blueprint('plans', __name__)


def signer():
    return URLSafeTimedSerializer(current_app.secret_key, salt='purchase-plan-v1')


@plans.route('/plans', methods=['GET', 'POST'])
@household_required
def index():
    sources = entries(g.household.id, 'source')
    source_id = request.form.get('source_id', type=int) if request.method == 'POST' else request.args.get('source_id', type=int)
    source = next((entry for entry in sources if entry.id == source_id), None)
    error, status = None, 200
    if request.method == 'POST':
        if not source:
            abort(404)
        try:
            try:
                review = signer().loads(request.form.get('review_token', ''), max_age=3600)
                if review['household'] != g.household.id or review['source'] != source.id:
                    raise BadSignature('scope')
            except (BadSignature, KeyError, TypeError):
                raise Conflict('Die Vorbereitung ist abgelaufen. Bitte neu pruefen.') from None
            plan = create_plan(g.household.id, source.id, review, request.form)
            db.session.commit()
            return redirect(url_for('plans.show', plan_id=plan.id))
        except ValueError as exc:
            db.session.rollback()
            # Refresh catalogue objects after rollback before rendering a new review.
            sources = entries(g.household.id, 'source')
            source = next((entry for entry in sources if entry.id == source_id), None)
            error, status = str(exc), 409 if isinstance(exc, Conflict) else 400
    rows = candidates(g.household.id, source) if source else []
    review_token = signer().dumps({'household': g.household.id, 'source': source.id,
        'source_version': source.version, 'request_id': str(uuid4()),
        'versions': {str(item.id): item.version for item, _, _ in rows},
        'offers': {str(item.id): [[offer.id, offer.version, offer.product.version] for offer in item_offers(item)]
            for item, _, _ in rows}}) if source else ''
    choices = {item.id: selected_offer([offer for offer in item_offers(item) if offer.active], source.name, available)
        for item, _, available in rows if available} if source else {}
    recent = db.session.scalars(select(PurchasePlan).where(PurchasePlan.household_id == g.household.id)
        .order_by(PurchasePlan.id.desc()).limit(20)).all()
    return render_template('plans.html', sources=sources, source=source, rows=rows,
        choices=choices, review_token=review_token, recent=recent, error=error), status


@plans.route('/plans/<int:plan_id>', methods=['GET', 'POST'])
@household_required
def show(plan_id):
    plan = db.session.scalar(select(PurchasePlan).where(PurchasePlan.id == plan_id,
        PurchasePlan.household_id == g.household.id))
    if not plan:
        abort(404)
    error, status = None, 200
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            if action == 'ordered' and request.form.get('confirm_ordered') != '1':
                raise ValueError('Bitte bestaetigen, dass du die Bestellung im Shop abgeschlossen hast.')
            change_plan(g.household.id, plan.id, request.form.get('version'), action, request.form.get('reference', ''))
            db.session.commit()
            flash('Vorhaben aktualisiert. Noch kein Wareneingang verbucht.', 'success')
            return redirect(url_for('plans.show', plan_id=plan.id))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), 409 if isinstance(exc, Conflict) else 400
    copy_text = '\n'.join([f'Einkauf bei {plan.source.name}', 'Zum manuellen Uebertragen in den Shop:', *[
        line_description(line) + ('\n' + line['url'] if line['url'] else '')
        for line in plan.lines if line['reserved']]])
    return render_template('plan.html', plan=plan, describe=line_description,
        copy_text=copy_text, error=error), status
