"""Personal settings and owner-only household administration."""
from functools import wraps

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import select

from .administration import (cancel_access, change_member, default_view_allowed, editable_view,
    locked_membership, clear_view_defaults, restore_entry, retire_entry, save_view, scoped, visible_views)
from .assortment import KINDS, entries, save_entry, version_matches
from .extensions import db
from .models import Household, Invitation, Membership, ShoppingView, User, utcnow
from .services import Conflict, clean_email, clean_text, make_invitation, validate_password
from .views import household_required

settings = Blueprint('settings', __name__, url_prefix='/settings')


def owner_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if g.membership.role != 'owner':
            abort(403)
        return function(*args, **kwargs)
    return household_required(wrapped)


def page(template, section, **context):
    return render_template(template, settings_section=section, **context)


def error_status(exc):
    return 409 if isinstance(exc, Conflict) else 400


@settings.get('/')
@household_required
def index():
    return redirect(url_for('settings.household' if g.membership.role == 'owner' else 'settings.profile'))


@settings.route('/profile', methods=['GET', 'POST'])
@household_required
def profile():
    error, status = None, 200
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            if action not in {'profile', 'credentials'}:
                raise ValueError('Bitte eine gültige Aktion wählen.')
            if action == 'credentials':
                from .auth import login_allowed
                if not login_allowed(current_user.email):
                    return page('settings/profile.html', 'profile', error='Zu viele Versuche. Bitte später erneut versuchen.', views=visible_views()), 429
            user = db.session.scalar(select(User).where(User.id == current_user.id).with_for_update().execution_options(populate_existing=True))
            version_matches(user, request.form.get('version'))
            if action == 'profile':
                user.name = clean_text(request.form.get('name'), 'Name', 80)
                layout = request.form.get('layout', 'household')
                if layout not in {'household','compact','cards'}:
                    raise ValueError('Bitte eine gültige Darstellung wählen.')
                default = default_view_allowed(request.form.get('default_view_id'))
                user.preferences = {**user.preferences, 'layout': layout, 'default_view_id': default}
            else:
                if not user.check_password(request.form.get('current_password', '')[:129]):
                    raise ValueError('Das aktuelle Passwort stimmt nicht.')
                email = clean_email(request.form.get('email'))
                if db.session.scalar(select(User.id).where(User.email == email, User.id != user.id)):
                    raise ValueError('Diese E-Mail-Adresse wird bereits verwendet.')
                password = request.form.get('password', '')
                if password:
                    validate_password(password)
                    if password != request.form.get('password_confirm'):
                        raise ValueError('Die neuen Passwörter stimmen nicht überein.')
                    user.set_password(password)
                user.email = email
                user.auth_version += 1
                cancel_access(user.id)
            db.session.commit()
            if action == 'credentials':
                login_user(user, fresh=True)
            flash('Dein Profil wurde gespeichert.' if action == 'profile' else 'Zugangsdaten gespeichert. Andere Sitzungen sind abgemeldet.', 'success')
            return redirect(url_for('settings.profile'))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), error_status(exc)
    return page('settings/profile.html', 'profile', error=error, views=visible_views()), status


@settings.route('/household', methods=['GET', 'POST'])
@owner_required
def household():
    error, status = None, 200
    if request.method == 'POST':
        try:
            home, actor = locked_membership()
            if request.form.get('action') == 'invite':
                invitation, token = make_invitation(actor, request.form.get('email'))
                db.session.commit()
                return page('settings/invite.html', 'household', invitation=invitation,
                    invite_url=current_app.config['PUBLIC_BASE_URL'].rstrip('/') + '/join#' + token)
            if request.form.get('action') != 'rename':
                raise ValueError('Bitte eine gültige Aktion wählen.')
            version_matches(home, request.form.get('version'))
            home.name = clean_text(request.form.get('name'), 'Haushaltsname', 100)
            db.session.commit()
            flash('Haushaltsname gespeichert.', 'success')
            return redirect(url_for('settings.household'))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), error_status(exc)
    members = db.session.scalars(select(Membership).where(Membership.household_id == g.household.id).order_by(Membership.active.desc(), Membership.id)).all()
    invitations = db.session.scalars(select(Invitation).where(Invitation.household_id == g.household.id,
        Invitation.consumed_at.is_(None), Invitation.revoked_at.is_(None), Invitation.expires_at > utcnow())).all()
    return page('settings/household.html', 'household', members=members, invitations=invitations, error=error), status


@settings.post('/members/<int:identifier>')
@owner_required
def member(identifier):
    try:
        changed = change_member(identifier, request.form.get('action'), request.form.get('version'), request.form.get('role'), request.form.get('name'), request.form.get('user_version'))
        is_self, active = changed.user_id == current_user.id, changed.active
        db.session.commit()
        if is_self and not active:
            logout_user()
            session.clear()
            response = redirect(url_for('auth.login'))
            response.headers['Clear-Site-Data'] = '"storage", "cache"'
            return response
        if is_self:
            login_user(current_user, fresh=True)
        flash('Zugang aktualisiert.', 'success')
        return redirect(url_for('settings.profile' if is_self and changed.role != 'owner' else 'settings.household'))
    except ValueError as exc:
        db.session.rollback()
        return page('settings/error.html', 'household', error=str(exc), back=url_for('settings.household')), error_status(exc)


@settings.post('/invitations/<int:identifier>/revoke')
@owner_required
def revoke_invitation(identifier):
    locked_membership()
    invitation = scoped(Invitation, identifier)
    invitation.revoked_at = utcnow()
    db.session.commit()
    flash('Einladung widerrufen.', 'success')
    return redirect(url_for('settings.household'))


@settings.route('/catalogue/<kind>', methods=['GET', 'POST'])
@owner_required
def catalogue(kind):
    if kind not in KINDS:
        abort(404)
    error, status = None, 200
    if request.method == 'POST':
        try:
            locked_membership()
            raw = request.form.get('entry_id')
            identifier = int(raw) if raw else None
            action = request.form.get('action')
            if action == 'save':
                entry = save_entry(g.household.id, kind, request.form.get('name'), identifier, request.form.get('version'))
                if kind == 'source' and 'shop_key' in request.form:
                    from .assortment import bind_shop
                    bind_shop(entry, request.form.get('shop_key'))
                message = 'Bezeichnung gespeichert.'
            elif action == 'retire' and identifier:
                replacement = int(request.form['replacement_id']) if request.form.get('replacement_id') else None
                outcome = retire_entry(kind, identifier, request.form.get('version'), replacement)
                message = 'Eintrag gelöscht.' if outcome == 'deleted' else 'Eintrag deaktiviert. Bisherige Daten bleiben erhalten.'
            elif action == 'restore' and identifier:
                restore_entry(kind, identifier, request.form.get('version'))
                message = 'Eintrag wieder aktiviert. Produktangebote bleiben unverändert.'
            else:
                raise ValueError('Bitte eine gültige Aktion wählen.')
            db.session.commit()
            flash(message, 'success')
            return redirect(url_for('settings.catalogue', kind=kind))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), error_status(exc)
    records = entries(g.household.id, kind, include_inactive=True)
    return page('settings/catalogue.html', 'categories' if kind == 'category' else 'sources',
        kind=kind, records=records, error=error), status


@settings.route('/shopping-views', methods=['GET', 'POST'])
@household_required
def shopping_views():
    if request.method == 'POST':
        return edit_shopping_view()
    return page('settings/views.html', 'views', views=visible_views())


@settings.route('/shopping-views/new', methods=['GET', 'POST'])
@settings.route('/shopping-views/<int:identifier>', methods=['GET', 'POST'])
@household_required
def edit_shopping_view(identifier=None):
    view = editable_view(identifier) if identifier else None
    error, status = None, 200
    if request.method == 'POST':
        try:
            if request.form.get('action') == 'delete' and identifier:
                locked_membership(False)
                view = editable_view(identifier)
                version_matches(view, request.form.get('version'))
                clear_view_defaults(view)
                db.session.delete(view)
            else:
                save_view(request.form, identifier)
            db.session.commit()
            flash('Einkaufsansichten gespeichert.', 'success')
            return redirect(url_for('settings.shopping_views'))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), error_status(exc)
    categories = entries(g.household.id, 'category', include_inactive=True)
    values = request.form if request.method == 'POST' else None
    order = list(view.category_order) if view else []
    if values:
        try:
            order = [int(value) for value in values.getlist('category_order')]
        except ValueError:
            order = []
    rank = {value: index for index, value in enumerate(order)}
    categories.sort(key=lambda entry: (rank.get(entry.id, len(rank)), entry.name.casefold(), entry.id))
    return page('settings/view_edit.html', 'views', view=view, categories=categories,
        sources=entries(g.household.id, 'source'), values=values, error=error), status


@settings.route('/app', methods=['GET', 'POST'])
@owner_required
def app_settings():
    error, status = None, 200
    if request.method == 'POST':
        try:
            home, actor = locked_membership()
            version_matches(home, request.form.get('version'))
            layout = request.form.get('layout')
            if layout not in {'compact','cards'}:
                raise ValueError('Bitte eine gültige Darstellung wählen.')
            default = default_view_allowed(request.form.get('default_view_id'), personal=False)
            home.settings = {**home.settings, 'layout': layout, 'default_view_id': default}
            db.session.commit()
            flash('Gemeinsame Vorgaben gespeichert.', 'success')
            return redirect(url_for('settings.app_settings'))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), error_status(exc)
    return page('settings/app.html', 'app', error=error, views=[view for view in visible_views() if view.user_id is None]), status
