"""Private PWA relay for an operator-started, time-limited browser login pilot."""
import json
from datetime import timedelta
from uuid import UUID, uuid4
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, select, update

from .extensions import db
from .models import ShopLogin, User, utcnow
from .services import membership_for
from .views import household_required

shop_login = Blueprint('shop_login', __name__)
SHOP_ORIGIN = 'https://www.galaxus.ch'
ACTIVE = ('queued', 'creating', 'running', 'pending', 'submitting', 'accepted')


def account_bound(household_id):
    """Deployment-level single-account pilot; no guessed/default household."""
    return str(current_app.config.get('GALAXUS_HOUSEHOLD_ID', '')) == str(household_id)


class ProviderUnavailable(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status
        self.status_code = status  # Safe HTTP metadata for the runner's redacted error report.


def api(method, path, body=None):
    """Fixed API host, bounded response, no retries or raw error disclosure."""
    req = Request('https://api.openai.com/v1/agents/sessions' + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization': 'Bearer ' + current_app.config['OPENAI_API_KEY'],
                 'OpenAI-Beta': 'agents=v1', 'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=15) as response:
            raw = response.read(512001)
        if len(raw) > 512000:
            raise ValueError()
        return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raise ProviderUnavailable('Shop-Verbindung derzeit nicht verfuegbar.', exc.code) from None
    except Exception:
        raise ProviderUnavailable('Shop-Verbindung derzeit nicht verfuegbar.') from None


def session_path(identifier):
    return '/' + quote(identifier, safe='')


def identity_valid(run):
    user = db.session.get(User, run.user_id, populate_existing=True)
    member = membership_for(run.user_id)
    return bool(user and user.active and user.auth_version == run.auth_version and member
                and member.household_id == run.household_id)


def owned(run_id):
    run = db.session.scalar(select(ShopLogin).where(ShopLogin.id == run_id,
        ShopLogin.user_id == current_user.id, ShopLogin.household_id == g.household.id,
        ShopLogin.auth_version == current_user.auth_version))
    if not run:
        abort(404)
    return run


def challenge(run):
    """No DB transaction remains open while reading the provider."""
    if (run.state != 'pending' or not run.session_id or run.expires_at <= utcnow()
            or not run.challenge_expires_at or run.challenge_expires_at <= utcnow()):
        abort(410)
    sid, rid, tid = run.session_id, run.request_id, run.turn_id
    db.session.rollback()
    session = api('GET', session_path(sid))
    if session.get('status') != 'requires_action':
        abort(410)
    action = next((a for a in session.get('required_actions', [])
        if a.get('type') == 'computer_use_approval_request' and a.get('request_id') == rid
        and a.get('turn_id') == tid and a.get('request', {}).get('type') == 'browser_authentication'), None)
    if not action or action['request'].get('credential_origin') != SHOP_ORIGIN:
        abort(410)
    return action['request']


def fields_for(schema, selected):
    fields, options = schema.get('fields', []), schema.get('options', [])
    if not isinstance(fields, list) or not isinstance(options, list) or len(fields) > 12 or len(options) > 12:
        abort(400)
    if any(not isinstance(f, dict) or not isinstance(f.get('id'), str) or not isinstance(f.get('label'), str)
           or type(f.get('required')) is not bool or not 1 <= len(f['id']) <= 128 or len(f['label']) > 256 for f in fields):
        abort(400)
    if any(not isinstance(o, dict) or not isinstance(o.get('id'), str) or not isinstance(o.get('label'), str)
           or not isinstance(o.get('field_ids'), list) or any(not isinstance(i, str) for i in o['field_ids']) for o in options):
        abort(400)
    if len({f['id'] for f in fields}) != len(fields):
        abort(400)
    if options:
        option = next((o for o in options if o['id'] == selected), None)
        if not option or any(i not in {f['id'] for f in fields} for i in option['field_ids']):
            abort(400)
        return [f for f in fields if f['id'] in option['field_ids']]
    if selected:
        abort(400)
    return fields


@shop_login.before_request
def gate():
    if not current_app.config['SHOP_LOGIN_PILOT_ENABLED'] or not current_app.config['OPENAI_API_KEY']:
        abort(404)


@shop_login.after_request
def private_headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    return response


@shop_login.route('/shop-login', methods=['GET', 'POST'])
@household_required
def index():
    if not account_bound(g.household.id):
        message = 'Fuer diesen Haushalt ist noch kein Galaxus-Konto eingerichtet.'
        if not current_app.config.get('GALAXUS_HOUSEHOLD_ID') and g.membership.role == 'owner':
            message += f' Fuer die Einrichtung ist eure Haushaltskennung {g.household.id}.'
        return render_template('error.html', message=message), 403
    if request.method == 'POST':
        if request.form.get('cost_consent') != 'yes':
            abort(400)
        try:
            start_id = str(UUID(request.form.get('start_request_id', '')))
        except ValueError:
            abort(400)
        old = db.session.scalar(select(ShopLogin).where(ShopLogin.user_id == current_user.id,
            ShopLogin.start_request_id == start_id))
        if old:
            if old.household_id != g.household.id or old.auth_version != current_user.auth_version:
                abort(409)
            return redirect(url_for('shop_login.login', run_id=old.id))
        if db.session.scalar(select(ShopLogin.id).where(ShopLogin.active_household_id == g.household.id)):
            abort(409)
        today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        count = db.session.scalar(select(func.count(ShopLogin.id)).where(
            ShopLogin.household_id == g.household.id, ShopLogin.created_at >= today))
        if count >= 2:
            return render_template('error.html', message='Heute sind bereits zwei Anmeldetests fuer euren Haushalt gestartet worden.'), 409
        run = ShopLogin(user_id=current_user.id, active_user_id=current_user.id,
            household_id=g.household.id, auth_version=current_user.auth_version,
            start_request_id=start_id, state='queued', cost_authorized_at=utcnow(),
            expires_at=utcnow() + timedelta(seconds=360))
        db.session.add(run)
        db.session.commit()
        return redirect(url_for('shop_login.login', run_id=run.id))
    runs = db.session.scalars(select(ShopLogin).where(ShopLogin.user_id == current_user.id,
        ShopLogin.household_id == g.household.id, ShopLogin.auth_version == current_user.auth_version)
        .order_by(ShopLogin.id.desc()).limit(5)).all()
    return render_template('shop_login_index.html', runs=runs, start_request_id=str(uuid4()))


@shop_login.route('/shop-login/<int:run_id>', methods=['GET', 'POST'])
@household_required
def login(run_id):
    run = owned(run_id)
    if request.method == 'POST' and request.form.get('action') == 'cancel':
        if run.state in ACTIVE:
            run.state = 'cancelled'
            db.session.commit()  # Operator watchdog performs remote cancellation/cleanup.
        return redirect(url_for('shop_login.login', run_id=run_id))
    if run.state != 'pending':
        return render_template('shop_login_form.html', run=run, schema=None)
    try:
        schema = challenge(run)
        # Membership/auth-version may have changed during the external request.
        db.session.expire_all()
        run = owned(run_id)
        if not identity_valid(run):
            abort(403)
        if (run.state != 'pending' or run.expires_at <= utcnow()
                or not run.challenge_expires_at or run.challenge_expires_at <= utcnow()):
            abort(410)
        selected = (request.args if request.method == 'GET' else request.form).get('option') or None
        fields = fields_for(schema, selected) if selected or not schema.get('options') else []
        if request.method == 'GET':
            return render_template('shop_login_form.html', run=run, schema=schema,
                                   selected=selected, fields=fields)
        if request.form.get('action') != 'submit':
            abort(400)
        if run.expires_at <= utcnow() or run.challenge_expires_at <= utcnow():
            abort(410)
        if request.form.get('request_id') != run.request_id or request.form.get('destination_confirmed') != 'yes':
            abort(409)
        fields = fields_for(schema, selected)
        allowed = {'csrf_token', 'request_id', 'option', 'destination_confirmed', 'action'}
        allowed.update('value_' + str(i) for i in range(len(fields)))
        if request.args or set(request.form) - allowed or any(len(request.form.getlist(k)) != 1 for k in request.form):
            abort(400)
        values = []
        for i, field in enumerate(fields):
            value = request.form.get('value_' + str(i), '')
            if len(value) > 2048 or (field['required'] and not value):
                abort(400)
            if value:
                values.append({'field_id': field['id'], 'value': value})
        if not selected and fields and not values:
            abort(400)
        sid, rid, tid = run.session_id, run.request_id, run.turn_id
        # Atomic reservation works across web workers; no lock held during HTTP.
        changed = db.session.execute(update(ShopLogin).where(ShopLogin.id == run_id,
            ShopLogin.state == 'pending', ShopLogin.request_id == rid, ShopLogin.turn_id == tid,
            ShopLogin.expires_at > utcnow(), ShopLogin.challenge_expires_at > utcnow())
            .values(state='submitting')).rowcount
        if changed != 1:
            db.session.rollback()
            abort(409)
        db.session.commit()
        response = {'type': 'browser_authentication', 'action': 'submit', 'fields': values}
        if selected:
            response['selected_option'] = selected
        try:
            api('POST', session_path(sid) + '/events', {'events': [{
                'type': 'agent.session.input.computer_use_approval_request_result',
                'request_id': rid, 'response': response}]})
            state = 'accepted'
        except ProviderUnavailable:
            state = 'unknown'
        db.session.execute(update(ShopLogin).where(ShopLogin.id == run_id,
            ShopLogin.state == 'submitting').values(state=state,
                auth_progress='manual_submitted' if state == 'accepted' else 'submission_unknown'))
        db.session.commit()
        return redirect(url_for('shop_login.login', run_id=run_id))
    except ProviderUnavailable:
        db.session.rollback()
        return render_template('error.html', message='Shop-Verbindung derzeit nicht verfuegbar. Bitte keine Eingaben erneut senden.'), 503
