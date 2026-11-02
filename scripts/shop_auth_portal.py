"""Ephemeral loopback-only login form for operator pilots. Never a public server."""
from secrets import compare_digest, token_urlsafe
from threading import Condition, Thread
from time import monotonic

from flask import Flask, abort, render_template_string, request
from werkzeug.serving import WSGIRequestHandler, make_server


PAGE = '''<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>James – Shop-Anmeldung</title><body>
<h1>Shop-Anmeldung</h1>
{% if message %}<p>{{ message }}</p><p><a href="">Aktualisieren</a></p>{% else %}
<p>Anmeldeziel: <strong>{{ origin }}</strong></p>
<p>Eingaben werden fuer diese Anmeldung an den OpenAI-gehosteten Shopbrowser
uebermittelt. James speichert sie nicht. Bitte das Anmeldeziel pruefen.</p>
{% if options and selected is none %}
<form method="get"><label>Anmeldemethode <select name="option">
{% for option in options %}<option value="{{ option.id }}">{{ option.label }}</option>{% endfor %}
</select></label><button type="submit">Methode auswaehlen</button></form>
{% else %}<form method="post" autocomplete="off">
<input type="hidden" name="csrf" value="{{ csrf }}">
<input type="hidden" name="request_id" value="{{ request_id }}">
<input type="hidden" name="option" value="{{ selected or '' }}">
{% for field in fields %}<p><label>{{ field.label }}
<input type="password" name="value_{{ loop.index0 }}" maxlength="2048"
autocomplete="off" {% if field.required %}required{% endif %}></label></p>{% endfor %}
<label><input type="checkbox" name="destination_confirmed" value="yes" required>
Ich habe das Anmeldeziel geprueft.</label>
<button type="submit" name="action" value="submit">Anmeldung uebermitteln</button>
</form>{% endif %}
<form method="post"><input type="hidden" name="csrf" value="{{ csrf }}">
<input type="hidden" name="request_id" value="{{ request_id }}">
<button type="submit" name="action" value="cancel">Abbrechen</button></form>
{% endif %}</body></html>'''


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass  # Capability URLs and form data never belong in access logs.


def checked_fields(challenge, selected):
    fields = challenge.fields
    if len(fields) > 12 or len({f.id for f in fields}) != len(fields):
        raise ValueError('Ungueltiges Anmeldeformular.')
    if challenge.options:
        option = next((o for o in challenge.options if o.id == selected), None)
        if not option or any(i not in {f.id for f in fields} for i in option.field_ids):
            raise ValueError('Anmeldemethode nicht verfuegbar.')
        return [f for f in fields if f.id in option.field_ids]
    if selected:
        raise ValueError('Unerwartete Anmeldemethode.')
    return fields


class LoginPortal:
    """One challenge, one submission; values exist only in the incoming request."""
    def __init__(self, allowed_origin):
        self.allowed_origin = allowed_origin
        self.token, self.csrf = token_urlsafe(32), token_urlsafe(32)
        self.condition = Condition()
        self.pending = None
        self.outcome = None
        self.deadline = 0
        self.server = None
        self.origin = None
        self.app = Flask(__name__)
        self.app.config.update(MAX_CONTENT_LENGTH=32 * 1024, MAX_FORM_PARTS=30,
                               MAX_FORM_MEMORY_SIZE=32 * 1024)
        self.app.add_url_rule('/' + self.token, 'login', self.view, methods=['GET', 'POST'])

        @self.app.after_request
        def headers(response):
            response.headers.update({
                'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
                'X-Content-Type-Options': 'nosniff',
                'Content-Security-Policy': "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
                'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
            })
            return response

    def start(self):
        self.server = make_server('127.0.0.1', 0, self.app, threaded=True, request_handler=QuietHandler)
        self.origin = 'http://127.0.0.1:' + str(self.server.server_port)
        Thread(target=self.server.serve_forever, daemon=True).start()
        return self.origin + '/' + self.token

    def close(self):
        with self.condition:
            self.outcome = self.outcome or 'cancelled'
            self.pending = None
            self.condition.notify_all()
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def handle(self, approval, client, session_id):
        if approval.request.credential_origin != self.allowed_origin:
            raise ValueError('Unbekanntes Anmeldeziel; keine Eingaben anfordern.')
        with self.condition:
            self.csrf = token_urlsafe(32)
            self.pending = (approval, client.with_options(max_retries=0), session_id)
            self.outcome = None
            self.deadline = monotonic() + 120
            while self.outcome is None and monotonic() < self.deadline:
                self.condition.wait(timeout=min(1, max(0, self.deadline - monotonic())))
            outcome = self.outcome
            self.pending = None
        if outcome != 'accepted':
            raise ValueError('Shop-Anmeldung abgebrochen oder Ausgang unklar; nicht automatisch wiederholen.')

    def current(self):
        if not self.pending or monotonic() >= self.deadline or self.outcome:
            abort(410)
        approval, client, session_id = self.pending
        try:
            session = client.beta.agents.sessions.retrieve(session_id)
        except Exception:
            abort(503)
        if session.status != 'requires_action':
            abort(410)
        fresh = next((a for a in session.required_actions
            if a.type == 'computer_use_approval_request' and a.request_id == approval.request_id
            and a.turn_id == approval.turn_id and a.request.type == 'browser_authentication'), None)
        if not fresh or fresh.request.credential_origin != self.allowed_origin:
            abort(410)
        return fresh, client, session_id

    def view(self):
        if request.host != self.origin.removeprefix('http://'):
            abort(403)
        with self.condition:
            if request.method == 'GET' and self.pending is None:
                return render_template_string(PAGE,
                    message='Noch keine offene Anmeldeanforderung. Bei Bedarf diese Seite aktualisieren.')
            if request.method == 'POST':
                if request.args:
                    abort(400)
                if request.headers.get('Origin') != self.origin:
                    abort(403)
                if not compare_digest(request.form.get('csrf', '').encode(), self.csrf.encode()):
                    abort(403)
            approval, client, session_id = self.current()
            selected = (request.args if request.method == 'GET' else request.form).get('option') or None
            if request.method == 'GET':
                try:
                    fields = checked_fields(approval.request, selected) if selected or not approval.request.options else []
                except ValueError:
                    abort(400)
                return render_template_string(PAGE, origin=self.allowed_origin,
                    options=approval.request.options, selected=selected, fields=fields,
                    csrf=self.csrf, request_id=approval.request_id)
            if request.form.get('request_id') != approval.request_id:
                abort(409)
            action = request.form.get('action')
            if action == 'cancel':
                response = {'type': 'browser_authentication', 'action': 'cancel'}
            elif action == 'submit':
                if request.form.get('destination_confirmed') != 'yes':
                    abort(400)
                try:
                    fields = checked_fields(approval.request, selected)
                except ValueError:
                    abort(400)
                allowed_keys = {'csrf', 'request_id', 'option', 'destination_confirmed', 'action'}
                allowed_keys.update('value_' + str(i) for i in range(len(fields)))
                if set(request.form) - allowed_keys or any(len(request.form.getlist(k)) != 1 for k in request.form):
                    abort(400)
                values = []
                for i, field in enumerate(fields):
                    value = request.form.get('value_' + str(i), '')
                    if len(value) > 2048 or (field.required and not value):
                        abort(400)
                    if value:
                        values.append({'field_id': field.id, 'value': value})
                if not selected and fields and not values:
                    abort(400)
                response = {'type': 'browser_authentication', 'action': 'submit', 'fields': values}
                if selected:
                    response['selected_option'] = selected
            else:
                abort(400)
            try:
                client.beta.agents.sessions.events.create(session_id, events=[{
                    'type': 'agent.session.input.computer_use_approval_request_result',
                    'request_id': approval.request_id, 'response': response}])
                self.outcome = 'accepted' if action == 'submit' else 'cancelled'
                message = 'Uebermittelt. Der Browser prueft die Anmeldung; Erfolg ist noch nicht bestaetigt.'
            except Exception:
                self.outcome = 'uncertain'
                message = 'Ausgang unklar. Keine automatische Wiederholung; Sitzung muss geprueft werden.'
            self.pending = None
            self.condition.notify_all()
            return render_template_string(PAGE, message=message), 200 if self.outcome == 'accepted' else 409
