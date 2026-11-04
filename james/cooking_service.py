"""Recipes share household articles, never a precise stock ledger."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from io import BytesIO
import json
import unicodedata
from uuid import UUID, uuid5
import warnings

from flask import abort
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select

from .assortment import lock_household, version_matches
from .extensions import db
from .models import (CookingAction, HouseholdItem, Recipe, RecipeCategory, RecipeIngredient,
    RecipeNote, ShoppingNeed, utcnow)
from .services import Conflict, change_item, clean_text, create_item

DEFAULT_CATEGORIES = ['Vorspeisen', 'Gerichte', 'Desserts', 'Snacks', 'Drinks']
LABELS = {'available': 'Vorrätig', 'low': 'Wird knapp', 'empty': 'Aufgebraucht', 'unknown': 'Bestand prüfen'}


def key(value):
    return unicodedata.normalize('NFKC', value).strip().casefold()


def optional(value, label, maximum):
    value = (value or '').strip()
    if len(value) > maximum or any(ord(c) < 32 and c not in '\n\r\t' for c in value):
        raise ValueError(f'{label}: Bitte höchstens {maximum} Zeichen eingeben.')
    return value


def number(value, label, maximum=9999):
    try:
        result = Decimal(str(value).replace(',', '.'))
        if not result.is_finite() or not 0 < result <= maximum or result.as_tuple().exponent < -3:
            raise InvalidOperation
        return result
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{label}: Bitte eine positive Zahl bis {maximum} mit höchstens drei Nachkommastellen eingeben.') from None


def amount_label(value):
    if value is None:
        return ''
    return format(Decimal(value).quantize(Decimal('.001'), rounding=ROUND_HALF_UP), 'f').rstrip('0').rstrip('.').replace('.', ',')


def categories(household_id):
    return db.session.scalars(select(RecipeCategory).where(RecipeCategory.household_id == household_id)
        .order_by(RecipeCategory.position, RecipeCategory.id)).all()


def ensure_categories(household_id):
    lock_household(household_id)
    if not categories(household_id):
        for position, name in enumerate(DEFAULT_CATEGORIES):
            db.session.add(RecipeCategory(household_id=household_id, name=name, name_key=key(name), position=position))
        db.session.flush()


def recipe_for(household_id, identifier, lock=False):
    query = select(Recipe).where(Recipe.id == identifier, Recipe.household_id == household_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    recipe = db.session.scalar(query)
    if not recipe:
        abort(404)
    return recipe


def ingredient_status(ingredient):
    item = ingredient.item
    if item.archived:
        return 'unknown'
    if ingredient.is_staple and item.stock_status == 'unknown':
        return 'available'
    return item.stock_status


def availability(recipe):
    statuses = [ingredient_status(line) for line in recipe.ingredients]
    missing = statuses.count('empty')
    uncertain = statuses.count('low') + statuses.count('unknown')
    state = 'missing' if missing else ('check' if uncertain or not statuses else 'ready')
    label = {'ready': 'Direkt kochbar', 'check': 'Bestand prüfen',
        'missing': '1 Zutat fehlt' if missing == 1 else f'{missing} Zutaten fehlen'}[state]
    return dict(state=state, label=label, missing=missing, uncertain=uncertain)


def read_image(upload):
    if not upload or not upload.filename:
        return None
    raw = upload.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Das Foto darf höchstens 4 MB gross sein.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as original:
                if original.width * original.height > 20_000_000:
                    raise ValueError('Bitte ein Foto mit höchstens 20 Megapixeln wählen.')
                image = ImageOps.exif_transpose(original).convert('RGB')
                image.thumbnail((1400, 1400))
                output = BytesIO()
                image.save(output, format='JPEG', quality=82)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Dieses Foto kann nicht gelesen werden. Bitte ein gültiges Bild wählen.') from None


def ingredient_values(form):
    fields = ['ingredient_name', 'ingredient_item', 'ingredient_amount', 'ingredient_unit', 'ingredient_group', 'ingredient_detail', 'ingredient_staple']
    columns = [form.getlist(field) for field in fields]
    length = len(columns[0])
    if length > 100 or any(len(column) != length for column in columns):
        raise ValueError('Bitte höchstens 100 vollständige Zutatenzeilen erfassen.')
    rows = []
    for values in zip(*columns):
        name, item_id, amount, unit, group, detail, staple = values
        if not name.strip() and not item_id and not amount and not unit and not group and not detail:
            continue
        rows.append(dict(name=clean_text(name, 'Zutat', 100), item_id=item_id,
            amount=number(amount, 'Zutatenmenge', 999999) if amount.strip() else None,
            unit=optional(unit, 'Einheit', 30), group=optional(group, 'Zutatengruppe', 60),
            detail=optional(detail, 'Zusatz', 160), is_staple=staple == '1'))
    if not rows:
        raise ValueError('Bitte mindestens eine Zutat erfassen.')
    return rows


def save_recipe(household_id, user_id, form, upload=None, identifier=None):
    lock_household(household_id)
    recipe = recipe_for(household_id, identifier, True) if identifier else None
    if recipe:
        version_matches(recipe, form.get('version'))
    category = db.session.scalar(select(RecipeCategory).where(RecipeCategory.household_id == household_id,
        RecipeCategory.id == form.get('category_id', type=int)))
    if not category or (not category.active and (not recipe or category.id != recipe.category_id)):
        raise ValueError('Bitte eine aktive Rezeptkategorie wählen.')
    title = clean_text(form.get('title'), 'Rezepttitel', 160)
    steps = [line.strip() for line in optional(form.get('steps'), 'Zubereitung', 20000).splitlines() if line.strip()]
    if not steps:
        raise ValueError('Bitte mindestens einen Zubereitungsschritt erfassen.')
    rows = ingredient_values(form)
    minutes = {}
    for field in ['prep_minutes', 'cook_minutes', 'rest_minutes']:
        try:
            value = int(form.get(field) or 0)
            if not 0 <= value <= 99999:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError('Zeitangaben: Bitte ganze Minuten von 0 bis 99999 eingeben.') from None
        minutes[field] = value
    source = optional(form.get('source'), 'Quelle', 1000)
    image = read_image(upload)
    values = dict(title=title, category_id=category.id, description=optional(form.get('description'), 'Beschreibung', 2000),
        servings=number(form.get('servings'), 'Grundmenge'), yield_unit=clean_text(form.get('yield_unit'), 'Mengeneinheit', 30),
        steps=steps, tags=list(dict.fromkeys(tag.strip() for tag in optional(form.get('tags'), 'Schlagwörter', 500).split(',') if tag.strip())),
        source=source, is_favorite=form.get('favorite') == '1', updated_by=user_id, updated_at=utcnow(), **minutes)
    if recipe is None:
        recipe = Recipe(household_id=household_id, created_by=user_id, **values)
        db.session.add(recipe)
    else:
        for name, value in values.items():
            setattr(recipe, name, value)
        recipe.version += 1
    if image is not None:
        recipe.image = image
    elif form.get('remove_image') == '1':
        recipe.image = None
    items = db.session.scalars(select(HouseholdItem).where(HouseholdItem.household_id == household_id)).all()
    mapped = {item.id: item for item in items}
    # Explicit selection wins. Automatic matching requires one exact normalized name.
    ingredients = []
    for position, row in enumerate(rows):
        identifier = row.pop('item_id')
        if identifier:
            try:
                item = mapped.get(int(identifier))
            except ValueError:
                item = None
            if not item or item.archived:
                raise ValueError('Bitte einen aktiven Artikel aus diesem Haushalt zuordnen.')
        else:
            matches = [item for item in items if not item.archived and key(item.name) == key(row['name'])]
            if len(matches) > 1:
                raise ValueError(f'«{row["name"]}» ist mehrfach vorhanden. Bitte den Artikel ausdrücklich zuordnen.')
            item = matches[0] if matches else create_item(household_id, {'name': row['name']})
            if not matches:
                items.append(item)
                mapped[item.id] = item
        ingredients.append(RecipeIngredient(item_id=item.id, position=position, **row))
    recipe.ingredients = ingredients
    db.session.flush()
    return recipe


def save_category(household_id, form):
    lock_household(household_id)
    raw = form.get('category_id', type=int)
    category = db.session.scalar(select(RecipeCategory).where(RecipeCategory.id == raw, RecipeCategory.household_id == household_id)) if raw else None
    if raw and category is None:
        abort(404)
    if category:
        version_matches(category, form.get('version'))
    action = form.get('action')
    if action == 'delete' and category:
        if db.session.scalar(select(Recipe.id).where(Recipe.category_id == category.id)):
            raise ValueError('Diese Kategorie wird verwendet. Bitte zuerst die Rezepte einer anderen Kategorie zuordnen oder die Kategorie deaktivieren.')
        if len(categories(household_id)) == 1:
            raise ValueError('Bitte mindestens eine Kategorie behalten.')
        db.session.delete(category)
    elif action == 'save':
        name = clean_text(form.get('name'), 'Kategorie', 60)
        if any(entry.name_key == key(name) and entry.id != raw for entry in categories(household_id)):
            raise ValueError('Diese Rezeptkategorie besteht bereits.')
        try:
            position = int(form.get('position') or 0)
            if not 0 <= position <= 999:
                raise ValueError
        except ValueError:
            raise ValueError('Reihenfolge: Bitte eine Zahl von 0 bis 999 eingeben.') from None
        if category is None:
            category = RecipeCategory(household_id=household_id)
            db.session.add(category)
        category.name, category.name_key, category.position = name, key(name), position
        category.active = form.get('active') == '1'
    else:
        raise ValueError('Bitte eine gültige Aktion wählen.')
    db.session.flush()


def apply_batch(household_id, user_id, identifier, form, action):
    lock_household(household_id)
    recipe = recipe_for(household_id, identifier, True)
    try:
        token = str(UUID(form.get('request_id', '')))
    except (ValueError, TypeError):
        raise ValueError('Bitte die Seite neu laden.') from None
    payload = {name: form.getlist(name) for name in sorted(form) if name not in {'csrf_token', 'request_id'}}
    fingerprint = sha256(json.dumps([identifier, action, payload], sort_keys=True).encode()).hexdigest()
    previous = db.session.scalar(select(CookingAction).where(CookingAction.household_id == household_id, CookingAction.request_id == token))
    if previous:
        if previous.fingerprint != fingerprint:
            raise Conflict('Diese Anfrage wurde bereits für eine andere Aktion verwendet.')
        return
    version_matches(recipe, form.get('version'))
    allowed = {line.item_id for line in recipe.ingredients}
    # One operation per article, including repeated ingredients in different groups.
    selected = form.getlist('item_id')
    if len(selected) > 100:
        raise ValueError('Zu viele Zutaten ausgewählt.')
    for raw in sorted(set(selected)):
        try:
            item_id = int(raw)
        except ValueError:
            raise ValueError('Ungültige Zutat.') from None
        if item_id not in allowed:
            abort(404)
        item = db.session.scalar(select(HouseholdItem).where(HouseholdItem.id == item_id,
            HouseholdItem.household_id == household_id).with_for_update().execution_options(populate_existing=True))
        if item is None:
            abort(404)
        version_matches(item, form.get(f'item_version_{item_id}'))
        event_token = str(uuid5(UUID(token), str(item_id)))
        if action == 'shopping':
            # Never change stock to low merely because an item is put on the list.
            wanted = number(form.get('servings', recipe.servings), 'Gewünschte Menge')
            factor = wanted / recipe.servings
            lines = [line for line in recipe.ingredients if line.item_id == item_id]
            amounts = '; '.join(f'{amount_label(line.amount * factor) if line.amount else ""} {line.unit} {line.name}'.strip() for line in lines)
            origin = {'recipe_id': recipe.id, 'title': recipe.title, 'amounts': amounts, 'yield': f'{amount_label(wanted)} {recipe.yield_unit}'}
            change_item(household_id, user_id, item_id, 'recipe_need', event_token, item.version,
                data={'recipe_origin': origin})
        else:
            status = form.get(f'status_{item_id}')
            if status not in {'available', 'low', 'empty'}:
                raise ValueError('Bitte einen gültigen Bestandsstatus wählen.')
            if item.stock_status != status:
                change_item(household_id, user_id, item_id, 'status', event_token, item.version, data={'stock_status': status})
    db.session.add(CookingAction(household_id=household_id, request_id=token, fingerprint=fingerprint))
    db.session.flush()
