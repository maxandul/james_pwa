"""Household recipe collection and owner-managed categories."""
from flask import Blueprint, flash, g, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.orm import selectinload, defer

from .cooking_service import (LABELS, amount_label, apply_batch, availability, categories, ensure_categories,
    ingredient_status, number, optional, recipe_for, save_category, save_recipe)
from .extensions import db
from .models import HouseholdItem, Recipe, RecipeIngredient, RecipeNote, ShoppingNeed
from .services import Conflict
from .assortment import lock_household, version_matches
from .settings import owner_required
from .views import household_required

cooking = Blueprint('cooking', __name__, url_prefix='/cooking')


@cooking.app_template_filter('recipe_amount')
def recipe_amount(value):
    return amount_label(value)


def error_response(exc):
    db.session.rollback()
    return render_template('cooking/error.html', error=str(exc)), 409 if isinstance(exc, Conflict) else 400


@cooking.get('')
@cooking.get('/')
@household_required
def index():
    ensure_categories(g.household.id)
    db.session.commit()
    query = (request.args.get('q') or '').strip()[:100].casefold()
    category = request.args.get('category', type=int)
    mode = request.args.get('filter', '')
    stmt = select(Recipe).where(Recipe.household_id == g.household.id).options(defer(Recipe.image),
        selectinload(Recipe.ingredients).selectinload(RecipeIngredient.item), selectinload(Recipe.category))
    if category:
        stmt = stmt.where(Recipe.category_id == category)
    recipes = db.session.scalars(stmt.order_by(Recipe.title, Recipe.id)).all()
    recipes = [r for r in recipes if not query or query in (r.title + ' ' + r.description + ' ' + ' '.join(r.tags) + ' ' + ' '.join(i.name for i in r.ingredients)).casefold()]
    states = {r.id: availability(r) for r in recipes}
    if mode == 'ready':
        recipes = [r for r in recipes if states[r.id]['state'] == 'ready']
    elif mode == 'favorites':
        recipes = [r for r in recipes if r.is_favorite]
    if request.args.get('sort') == 'missing':
        recipes.sort(key=lambda r: (states[r.id]['missing'] + states[r.id]['uncertain'], states[r.id]['missing'], r.title.casefold(), r.id))
    page = max(1, request.args.get('page', 1, type=int))
    pages = max(1, (len(recipes) + 23) // 24)
    page = min(page, pages)
    visible = recipes[(page-1)*24:page*24]
    image_ids = set(db.session.scalars(select(Recipe.id).where(Recipe.id.in_([r.id for r in visible]), Recipe.image.is_not(None))).all())
    return render_template('cooking/index.html', recipes=visible, states=states, image_ids=image_ids,
        categories=categories(g.household.id), query=query, selected_category=category, mode=mode, page=page, pages=pages,
        previous=url_for('cooking.index', **{**request.args.to_dict(), 'page': page-1}),
        following=url_for('cooking.index', **{**request.args.to_dict(), 'page': page+1}))


@cooking.route('/new', methods=['GET', 'POST'])
@cooking.route('/<int:identifier>/edit', methods=['GET', 'POST'])
@household_required
def edit(identifier=None):
    ensure_categories(g.household.id)
    db.session.commit()
    recipe = recipe_for(g.household.id, identifier) if identifier else None
    error, status = None, 200
    if request.method == 'POST':
        try:
            recipe = save_recipe(g.household.id, current_user.id, request.form, request.files.get('image'), identifier)
            db.session.commit()
            flash('Rezept gespeichert.', 'success')
            return redirect(url_for('cooking.show', identifier=recipe.id))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), 409 if isinstance(exc, Conflict) else 400
    if request.method == 'POST':
        values = request.form
        fields = ['name', 'item', 'amount', 'unit', 'group', 'detail', 'staple']
        lists = [request.form.getlist('ingredient_' + field) for field in fields]
        rows = [dict(zip(fields, parts)) for parts in zip(*lists)]
    else:
        values = {field: getattr(recipe, field) for field in ['title', 'description', 'category_id', 'yield_unit', 'prep_minutes', 'cook_minutes', 'rest_minutes', 'source']} if recipe else {}
        values.update(servings=amount_label(recipe.servings) if recipe else '4',
            favorite='1' if recipe and recipe.is_favorite else '',
            steps='\n'.join(recipe.steps) if recipe else '', tags=', '.join(recipe.tags) if recipe else '')
        rows = [dict(name=i.name, item=str(i.item_id), amount=amount_label(i.amount), unit=i.unit,
            group=i.group, detail=i.detail, staple='1' if i.is_staple else '0') for i in recipe.ingredients] if recipe else [{} for _ in range(3)]
    items = db.session.scalars(select(HouseholdItem).where(HouseholdItem.household_id == g.household.id,
        ((HouseholdItem.archived.is_(False)) | (HouseholdItem.id.in_([i.item_id for i in recipe.ingredients] if recipe else [])))).order_by(HouseholdItem.name, HouseholdItem.id)).all()
    return render_template('cooking/edit.html', recipe=recipe, values=values, rows=rows, categories=categories(g.household.id),
        items=items, error=error, conflict=status == 409), status


@cooking.get('/<int:identifier>')
@household_required
def show(identifier):
    recipe = recipe_for(g.household.id, identifier)
    try:
        servings = number(request.args.get('servings', recipe.servings), 'Gewünschte Menge')
    except ValueError as exc:
        return error_response(exc)
    unique = {i.item_id: i.item for i in recipe.ingredients}
    needs = dict(db.session.execute(select(ShoppingNeed.item_id, ShoppingNeed.quantity).where(ShoppingNeed.item_id.in_(unique))).all())
    return render_template('cooking/show.html', recipe=recipe, state=availability(recipe), servings=servings,
        factor=servings/recipe.servings, statuses=LABELS, ingredient_status=ingredient_status, unique_items=unique.values(), needs=needs)


@cooking.get('/<int:identifier>/image')
@household_required
def image(identifier):
    recipe = recipe_for(g.household.id, identifier)
    response = make_response(recipe.image or b'', 200 if recipe.image else 404)
    response.mimetype = 'image/jpeg'
    response.headers['Cache-Control'] = 'no-store'
    return response


@cooking.post('/<int:identifier>/action')
@household_required
def action(identifier):
    try:
        operation = request.form.get('action')
        if operation in {'shopping', 'stock'}:
            apply_batch(g.household.id, current_user.id, identifier, request.form, operation)
            message = 'Einkaufsliste ergänzt. Bereits offene Positionen bleiben unverändert.' if operation == 'shopping' else 'Bestand aktualisiert. Es wurden keine Mengen abgezogen.'
        else:
            lock_household(g.household.id)
            recipe = recipe_for(g.household.id, identifier, True)
            version_matches(recipe, request.form.get('version'))
            if operation == 'delete':
                db.session.delete(recipe)
                message = 'Rezept gelöscht. Haushaltsartikel und Einkaufsliste bleiben erhalten.'
            elif operation == 'favorite':
                recipe.is_favorite = request.form.get('favorite') == '1'
                recipe.version += 1
                message = 'Favorit gespeichert.'
            elif operation == 'note':
                text = optional(request.form.get('note'), 'Notiz', 4000)
                if not text:
                    raise ValueError('Bitte eine Notiz eingeben.')
                recipe.notes.append(RecipeNote(user_id=current_user.id, text=text))
                recipe.version += 1
                message = 'Notiz gespeichert.'
            else:
                raise ValueError('Bitte eine gültige Aktion wählen.')
        db.session.commit()
        flash(message, 'success')
        return redirect(url_for('cooking.index') if operation == 'delete' else url_for('cooking.show', identifier=identifier))
    except ValueError as exc:
        return error_response(exc)


@cooking.route('/categories', methods=['GET', 'POST'])
@owner_required
def manage_categories():
    ensure_categories(g.household.id)
    db.session.commit()
    error, status = None, 200
    if request.method == 'POST':
        try:
            save_category(g.household.id, request.form)
            db.session.commit()
            flash('Rezeptkategorien gespeichert.', 'success')
            return redirect(url_for('cooking.manage_categories'))
        except ValueError as exc:
            db.session.rollback()
            error, status = str(exc), 409 if isinstance(exc, Conflict) else 400
    return render_template('cooking/categories.html', settings_section='recipes', categories=categories(g.household.id), error=error), status
