"""Resolve saved shopping views without changing demand or stock."""
from flask import abort, g
from flask_login import current_user
from sqlalchemy import or_, select

from .extensions import db
from .models import Category, ShoppingView


def available_views():
    return db.session.scalars(select(ShoppingView).where(ShoppingView.household_id == g.household.id,
        or_(ShoppingView.user_id.is_(None), ShoppingView.user_id == current_user.id)).order_by(ShoppingView.name, ShoppingView.id)).all()


def resolve_view(args):
    views = available_views()
    by_id = {view.id: view for view in views}
    source = args.get('source', '')[:60]
    if 'view_id' in args:
        try:
            identifier = int(args.get('view_id') or 0)
        except ValueError:
            abort(404)
        if identifier and identifier not in by_id:
            abort(404)
        selected = by_id.get(identifier)
    else:
        selected = None
        if not source:
            for identifier in (current_user.preferences.get('default_view_id'), g.household.settings.get('default_view_id')):
                candidate = by_id.get(identifier)
                if candidate and (not candidate.source or candidate.source.active):
                    selected = candidate
                    break
        if not selected:
            matching = [view for view in views if view.is_default and
                ((view.source and view.source.active and view.source.name == source) if source else view.source_id is None)]
            selected = next((view for view in matching if view.user_id == current_user.id), None) or next(
                (view for view in matching if view.user_id is None), None)
    if selected:
        source = selected.source.name if selected.source else ''
    return selected, source, views


def arrange(rows, view):
    categories = db.session.scalars(select(Category).where(Category.household_id == g.household.id)).all() if view else []
    by_name = {entry.name: entry.id for entry in categories}
    original = len(rows)
    if view and view.category_ids:
        selected = set(view.category_ids)
        rows = [(item, need) for item, need in rows if by_name.get(item.category) in selected]
    order = {identifier: index for index, identifier in enumerate(view.category_order)} if view else {}
    category_key = lambda item: (order.get(by_name.get(item.category), len(order)), item.category.casefold(), item.category)
    # Sort each group explicitly: Jinja groupby would undo the configured aisle order.
    groups = {}
    for item, need in rows:
        groups.setdefault(item.category, []).append((item, need))
    for values in groups.values():
        if view and view.item_sort == 'favorites':
            values.sort(key=lambda row: (not row[0].is_favorite, row[0].name.casefold(), row[0].id))
        else:
            values.sort(key=lambda row: (row[0].name.casefold(), row[0].id), reverse=bool(view and view.item_sort == 'name_desc'))
    ordered = sorted(groups.items(), key=lambda group: category_key(group[1][0][0]))
    return rows, ordered, original - len(rows)
