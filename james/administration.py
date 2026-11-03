"""Household-scoped administration. Callers own commit/rollback."""
from flask import abort, g
from sqlalchemy import func, or_, select, update

from .assortment import KINDS, entries, key, lock_household, version_matches
from .extensions import db
from .models import (Activity, Category, Household, HouseholdItem, Invitation, ItemSource,
    Membership, Product, PurchasePlan, PurchaseSource, ShopLogin, ShopOffer, ShoppingView, User, utcnow)
from .services import Conflict, clean_text


def locked_membership(require_owner=True):
    home = lock_household(g.household.id)
    member = db.session.scalar(select(Membership).where(Membership.id == g.membership.id,
        Membership.household_id == home.id, Membership.active.is_(True)).with_for_update().execution_options(populate_existing=True))
    if not member or (require_owner and member.role != 'owner'):
        abort(403)
    return home, member


def scoped(model, identifier):
    entry = db.session.get(model, identifier)
    if not entry or entry.household_id != g.household.id:
        abort(404)
    return entry


def cancel_access(user_id):
    db.session.execute(update(ShopLogin).where(ShopLogin.user_id == user_id,
        ShopLogin.state.in_(('queued','creating','running','pending','submitting','accepted'))).values(state='cancelled'))


def change_member(identifier, action, version, role=None, name=None, user_version=None):
    home, actor = locked_membership()
    member = db.session.scalar(select(Membership).where(Membership.id == identifier,
        Membership.household_id == home.id).with_for_update().execution_options(populate_existing=True))
    if not member:
        abort(404)
    version_matches(member, version)
    if action not in {'role', 'remove', 'restore'}:
        raise ValueError('Bitte eine gültige Aktion wählen.')
    next_role = role if action == 'role' else ('member' if action == 'restore' else member.role)
    if next_role not in {'owner', 'member'}:
        raise ValueError('Bitte eine gültige Rolle wählen.')
    if name is not None and action == 'role':
        version_matches(member.user, user_version)
        member.user.name = clean_text(name, 'Name', 80)
    if member.active and member.user.active and member.role == 'owner' and (action == 'remove' or next_role != 'owner'):
        owners = db.session.scalar(select(func.count()).select_from(Membership).join(User).where(
            Membership.household_id == home.id, Membership.active.is_(True), Membership.role == 'owner', User.active.is_(True)))
        if owners <= 1:
            raise Conflict('Mindestens eine aktive Person muss die Haushaltsverwaltung behalten.')
    if action == 'role' and not member.active:
        raise Conflict('Den Zugang zuerst wieder aktivieren.')
    if action == 'role' and member.role == next_role:
        return member
    member.role = next_role
    member.active = action != 'remove'
    if action == 'restore':
        member.user.active = True
    # Role/access changes invalidate old sessions and pending private browser tasks.
    member.user.auth_version += 1
    cancel_access(member.user_id)
    db.session.execute(update(Invitation).where(Invitation.household_id == home.id,
        Invitation.created_by == member.user_id, Invitation.consumed_at.is_(None)).values(revoked_at=utcnow()))
    return member


def visible_views(user_id=None):
    from flask_login import current_user
    user_id = user_id or current_user.id
    return db.session.scalars(select(ShoppingView).where(ShoppingView.household_id == g.household.id,
        or_(ShoppingView.user_id.is_(None), ShoppingView.user_id == user_id)).order_by(
            ShoppingView.name, ShoppingView.id)).all()


def editable_view(identifier):
    from flask_login import current_user
    view = scoped(ShoppingView, identifier)
    if view.user_id != current_user.id and not (view.user_id is None and g.membership.role == 'owner'):
        abort(403)
    return view


def parse_ids(values, valid, label):
    try:
        ids = [int(value) for value in values]
    except (TypeError, ValueError):
        raise ValueError(f'{label}: Bitte gültige Einträge wählen.') from None
    if len(ids) != len(set(ids)) or not set(ids).issubset(valid):
        raise ValueError(f'{label}: Bitte nur Einträge aus eurem Haushalt wählen.')
    return ids


def save_view(data, identifier=None):
    from flask_login import current_user
    home, member = locked_membership(False)
    view = editable_view(identifier) if identifier else ShoppingView(household_id=home.id)
    if identifier:
        version_matches(view, data.get('version'))
    shared = data.get('scope') == 'shared'
    if shared and member.role != 'owner':
        abort(403)
    if data.get('scope') not in {'shared', 'personal'}:
        raise ValueError('Bitte persönlich oder gemeinsam wählen.')
    user_id = None if shared else current_user.id
    # Personal views cannot silently be appropriated by another administrator.
    if identifier and view.user_id not in {None, current_user.id}:
        abort(403)
    if identifier and view.source and not view.source.active and 'source_id' not in data:
        raise ValueError('Bitte einen aktiven Einkaufsort oder ausdrücklich alle Einkaufsorte wählen.')
    try:
        source_id = int(data['source_id']) if data.get('source_id') else None
    except ValueError:
        raise ValueError('Bitte einen gültigen Einkaufsort wählen.') from None
    if source_id is not None:
        source = scoped(PurchaseSource, source_id)
        if not source.active:
            raise ValueError('Bitte einen aktiven Einkaufsort wählen.')
    valid = {entry.id for entry in entries(home.id, 'category', include_inactive=True)}
    order = parse_ids(data.getlist('category_order'), valid, 'Reihenfolge')
    selected = parse_ids(data.getlist('category_ids'), valid, 'Warengruppen')
    sort = data.get('item_sort', 'name')
    if sort not in {'name', 'name_desc', 'favorites'}:
        raise ValueError('Bitte eine gültige Sortierung wählen.')
    name = clean_text(data.get('name'), 'Name der Einkaufsansicht', 100)
    default = data.get('is_default') == '1'
    if default:
        others = db.session.scalars(select(ShoppingView).where(ShoppingView.household_id == home.id,
            ShoppingView.user_id == user_id if user_id is not None else ShoppingView.user_id.is_(None),
            ShoppingView.source_id == source_id if source_id is not None else ShoppingView.source_id.is_(None),
            ShoppingView.is_default.is_(True))).all()
        for other in others:
            if other.id != view.id:
                other.is_default = False
    if identifier and view.user_id is None and user_id is not None:
        clear_view_defaults(view, keep_user_id=user_id)
    view.name, view.user_id, view.source_id = name, user_id, source_id
    view.category_ids, view.category_order, view.item_sort, view.is_default = selected, order, sort, default
    db.session.add(view)
    db.session.flush()
    return view


def default_view_allowed(identifier, personal=True):
    if not identifier:
        return None
    try:
        view = scoped(ShoppingView, int(identifier))
    except (ValueError, TypeError):
        raise ValueError('Bitte eine gültige Standardansicht wählen.') from None
    from flask_login import current_user
    if view.user_id is not None and (not personal or view.user_id != current_user.id):
        abort(403)
    if view.source and not view.source.active:
        raise ValueError('Der Einkaufsort dieser Ansicht ist inaktiv.')
    return view.id


def catalogue_usage(entry, kind):
    field = HouseholdItem.category if kind == 'category' else HouseholdItem.source
    names = {entry.name_key, *entry.aliases}
    items = db.session.scalars(select(HouseholdItem).where(HouseholdItem.household_id == entry.household_id)).all()
    count = sum(key(getattr(item, field.key)) in names for item in items)
    json_field = 'category' if kind == 'category' else 'source'
    # Match the same NFKC/casefold keys as aliases, including historical spellings.
    # Stream projected labels rather than loading the household's activity objects.
    labels = db.session.execute(select(Activity.before_state[json_field].as_string(),
        Activity.after_state[json_field].as_string()).where(
            Activity.household_id == entry.household_id)).yield_per(250)
    try:
        history = any(key(label) in names for row in labels for label in row if isinstance(label, str))
    finally:
        labels.close()
    views = db.session.scalars(select(ShoppingView).where(ShoppingView.household_id == entry.household_id)).all()
    count += history
    home = db.session.get(Household, entry.household_id)
    count += sum(value == entry.id for name, value in home.settings.get('catalogue_redirects', {}).items() if name.startswith(kind + ':'))
    if kind == 'category':
        count += sum(entry.id in view.category_ids or entry.id in view.category_order for view in views)
    else:
        count += sum(view.source_id == entry.id for view in views)
        for model in (ItemSource, ShopOffer, PurchasePlan):
            count += db.session.scalar(select(func.count()).select_from(model).where(model.source_id == entry.id))
    return count


def retire_entry(kind, identifier, version, replacement_id=None):
    home, member = locked_membership()
    if kind not in KINDS:
        abort(404)
    entry = scoped(KINDS[kind], identifier)
    version_matches(entry, version)
    replacement = scoped(KINDS[kind], replacement_id) if replacement_id is not None else None
    if replacement and (replacement.id == entry.id or not replacement.active):
        raise ValueError('Bitte einen anderen aktiven Ersatz wählen.')
    used = catalogue_usage(entry, kind)
    keys = {entry.name_key, *entry.aliases}
    touched = set()
    if replacement:
        field = 'category' if kind == 'category' else 'source'
        items = db.session.scalars(select(HouseholdItem).where(HouseholdItem.household_id == home.id).with_for_update()).all()
        if kind == 'source':
            old_offers = db.session.scalars(select(ShopOffer).where(ShopOffer.household_id == home.id,
                ShopOffer.source_id == entry.id)).all()
            target_offers = db.session.scalars(select(ShopOffer).where(ShopOffer.household_id == home.id,
                ShopOffer.source_id == replacement.id)).all()
            target_products = {offer.product_id for offer in target_offers}
            if any(offer.product_id in target_products for offer in old_offers):
                raise Conflict('Ein Produkt ist an beiden Einkaufsorten hinterlegt. Bitte die doppelten Produktzuordnungen zuerst bereinigen oder den Ort ohne Ersatz deaktivieren.')
            preferred_items = {offer.product.item_id for offer in target_offers if offer.active and offer.preferred}
            for offer in old_offers:
                touched.add(offer.product.item_id)
                offer.source_id = replacement.id
                if offer.product.item_id in preferred_items:
                    offer.preferred = False
            links = db.session.scalars(select(ItemSource).where(ItemSource.source_id == entry.id)).all()
            for link in links:
                touched.add(link.item_id)
                if not db.session.get(ItemSource, (link.item_id, replacement.id)):
                    db.session.add(ItemSource(item_id=link.item_id, source_id=replacement.id))
                db.session.delete(link)
        for item in items:
            if key(getattr(item, field)) in keys:
                setattr(item, field, replacement.name)
                item.version += 1
            elif item.id in touched:
                item.version += 1
        for view in db.session.scalars(select(ShoppingView).where(ShoppingView.household_id == home.id)).all():
            if kind == 'category':
                for field in ('category_order', 'category_ids'):
                    values = list(dict.fromkeys(replacement.id if value == entry.id else value for value in getattr(view, field)))
                    setattr(view, field, values)
            elif view.source_id == entry.id:
                # Do not create conflicting defaults after merging two locations.
                view.source_id = replacement.id
                view.is_default = False
        settings = dict(home.settings)
        redirects = {name: replacement.id if name.startswith(kind + ':') and value == entry.id else value
            for name, value in settings.get('catalogue_redirects', {}).items()}
        redirects.update({f'{kind}:{name}': replacement.id for name in keys})
        settings['catalogue_redirects'] = redirects
        home.settings = settings
    if used or replacement:
        entry.active = False
        if kind == 'source' and not replacement:
            for offer in db.session.scalars(select(ShopOffer).where(ShopOffer.household_id == home.id, ShopOffer.source_id == entry.id)).all():
                touched.add(offer.product.item_id)
                offer.active = False
                offer.preferred = False
        if not replacement:
            field = 'category' if kind == 'category' else 'source'
            for item in db.session.scalars(select(HouseholdItem).where(HouseholdItem.household_id == home.id)).all():
                if key(getattr(item, field)) in keys or item.id in touched:
                    item.version += 1
        return 'deactivated'
    settings = dict(home.settings)
    settings['catalogue_deleted'] = sorted(set(settings.get('catalogue_deleted', [])) | {f'{kind}:{name}' for name in keys})
    home.settings = settings
    db.session.delete(entry)
    return 'deleted'


def restore_entry(kind, identifier, version):
    home, actor = locked_membership()
    if kind not in KINDS:
        abort(404)
    entry = scoped(KINDS[kind], identifier)
    version_matches(entry, version)
    settings = dict(home.settings)
    redirects = dict(settings.get('catalogue_redirects', {}))
    for value in (entry.name_key, *entry.aliases):
        redirects.pop(f'{kind}:{value}', None)
    settings['catalogue_redirects'] = redirects
    home.settings = settings
    entry.active = True


def clear_view_defaults(view, keep_user_id=None):
    home = db.session.get(Household, view.household_id)
    if home.settings.get('default_view_id') == view.id:
        home.settings = {**home.settings, 'default_view_id': None}
    users = db.session.scalars(select(User).join(Membership).where(Membership.household_id == view.household_id)).all()
    for user in users:
        if user.id != keep_user_id and user.preferences.get('default_view_id') == view.id:
            user.preferences = {**user.preferences, 'default_view_id': None}
