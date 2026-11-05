from io import BytesIO
from uuid import uuid4

from PIL import Image
from sqlalchemy import select
from werkzeug.datastructures import MultiDict

from james.extensions import db
from james.models import (Activity, CookingAction, HouseholdItem, Recipe, RecipeCategory, RecipeIngredient,
    RecipeNote, ShoppingNeed)
from james.cooking_service import availability
from test_app import csrf, login, seed_item


def recipe_form(client, **changes):
    token = csrf(client, '/cooking/new')
    with client.application.app_context():
        category = changes.get('category_id') or db.session.scalar(select(RecipeCategory).where(RecipeCategory.name == 'Gerichte').order_by(RecipeCategory.id)).id
    fields = dict(csrf_token=token, title='Quark-Spätzli', category_id=str(category), servings='4',
        yield_unit='Portionen', steps='Zutaten verrühren.\nTeig ruhen lassen.\nSpätzli kochen.', tags='schnell, vegetarisch',
        ingredient_name=['Eier', 'Mehl'], ingredient_item=['', ''], ingredient_amount=['3', '300'],
        ingredient_unit=['Stück', 'g'], ingredient_group=['Teig', 'Teig'], ingredient_detail=['', 'gesiebt'],
        ingredient_staple=['0', '0'])
    fields.update(changes)
    return MultiDict([(key, part) for key, value in fields.items() for part in (value if isinstance(value, list) else [value])])


def create_recipe(client, **changes):
    result = client.post('/cooking/new', data=recipe_form(client, **changes))
    assert result.status_code == 302, result.get_data(as_text=True)
    identifier = int(result.location.split('/')[-1])
    return identifier


def action_form(client, recipe_id, action, selected=None, **changes):
    with client.application.app_context():
        recipe = db.session.get(Recipe, recipe_id)
        data = dict(csrf_token=csrf(client, f'/cooking/{recipe_id}'), action=action,
            version=str(recipe.version), request_id=str(uuid4()), item_id=selected or [])
        for ingredient in recipe.ingredients:
            data[f'item_version_{ingredient.item_id}'] = str(ingredient.item.version)
    data.update(changes)
    return data


def test_collection_create_edit_render_and_scaling(client, app):
    login(client)
    identifier = create_recipe(client)
    result = client.get(f'/cooking/{identifier}?servings=6')
    assert result.status_code == 200
    html = result.get_data(as_text=True)
    assert '4,5 Stück Eier' in html and '450 g Mehl' in html
    assert 'Bestand prüfen' in html
    assert client.get('/cooking?filter=ready').get_data(as_text=True).count('Quark-Spätzli') == 0
    with app.app_context():
        recipe = db.session.get(Recipe, identifier)
        assert len(recipe.steps) == 3
        assert len(recipe.ingredients) == 2
        assert all(i.item.stock_status == 'unknown' for i in recipe.ingredients)
        assert all(i.item.default_quantity == 1 for i in recipe.ingredients)
    for path in ['/cooking', f'/cooking/{identifier}/edit', '/cooking/categories']:
        assert client.get(path).status_code == 200
    form = recipe_form(client, version='1', title='Quarkknöpfli')
    assert client.post(f'/cooking/{identifier}/edit', data=form).status_code == 302
    with app.app_context():
        assert db.session.scalar(select(Recipe)).title == 'Quarkknöpfli'
        assert len(db.session.scalars(select(HouseholdItem)).all()) == 2


def test_available_low_missing_unknown_and_staples(client, app):
    login(client)
    identifier = create_recipe(client, ingredient_staple=['0', '1'])
    with app.app_context():
        recipe = db.session.get(Recipe, identifier)
        recipe.ingredients[0].item.stock_status = 'available'
        db.session.commit()
        assert availability(recipe)['state'] == 'ready'
        recipe.ingredients[1].item.stock_status = 'low'
        assert availability(recipe)['state'] == 'check'
        recipe.ingredients[1].item.stock_status = 'empty'
        assert availability(recipe)['state'] == 'missing'
        db.session.commit()
    assert 'Quark-Spätzli' not in client.get('/cooking?filter=ready').get_data(as_text=True)
    html = client.get(f'/cooking/{identifier}').get_data(as_text=True)
    assert '1 Zutat fehlt' in html


def test_shopping_defaults_no_stock_change_replay_and_partial_purchase(client, app):
    login(client)
    identifier = create_recipe(client)
    with app.app_context():
        recipe = db.session.get(Recipe, identifier)
        ids = [line.item_id for line in recipe.ingredients]
        for line in recipe.ingredients:
            line.item.stock_status = 'empty'
            line.item.default_quantity = 2
        db.session.commit()
    data = action_form(client, identifier, 'shopping', list(map(str, ids)))
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 302
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 302
    with app.app_context():
        assert [need.quantity for need in db.session.scalars(select(ShoppingNeed).order_by(ShoppingNeed.id))] == [2, 2]
        assert all(item.stock_status == 'empty' for item in db.session.scalars(select(HouseholdItem)))
        assert len(db.session.scalars(select(Activity)).all()) == 2
        assert len(db.session.scalars(select(CookingAction)).all()) == 1
    html = client.get('/shopping').get_data(as_text=True)
    assert 'Für Quark-Spätzli' in html and '300 g Mehl' in html
    data = action_form(client, identifier, 'shopping', list(map(str, ids)))
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 302
    from test_app import action
    with app.app_context():
        version = db.session.get(HouseholdItem, ids[0]).version
    assert action(client, ids[0], 'purchase', version, quantity=1).status_code == 302
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == ids[0])).quantity == 1
        assert db.session.get(HouseholdItem, ids[0]).stock_status == 'available'


def test_stock_correction_and_replay_do_not_touch_shopping(client, app):
    login(client)
    identifier = create_recipe(client)
    with app.app_context():
        item_id = db.session.get(Recipe, identifier).ingredients[0].item_id
    data = action_form(client, identifier, 'stock', [str(item_id)], **{f'status_{item_id}': 'low'})
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 302
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 302
    with app.app_context():
        assert db.session.get(HouseholdItem, item_id).stock_status == 'low'
        assert db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == item_id)).quantity == 0
    data[f'status_{item_id}'] = 'empty'
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 409


def test_household_isolation_categories_and_csrf(client, app):
    login(client)
    identifier = create_recipe(client)
    other = app.test_client()
    login(other, 'other@example.test')
    for path in [f'/cooking/{identifier}', f'/cooking/{identifier}/edit', f'/cooking/{identifier}/image']:
        assert other.get(path).status_code == 404
    assert other.post(f'/cooking/{identifier}/action', data={'csrf_token': csrf(other, '/'), 'action': 'delete'}).status_code == 404
    assert client.post(f'/cooking/{identifier}/action', data={'action': 'delete'}).status_code == 400
    member = app.test_client()
    login(member, 'member@example.test')
    assert member.get('/cooking/categories').status_code == 403
    assert member.get(f'/cooking/{identifier}').status_code == 200
    with app.app_context():
        foreign = db.session.scalar(select(HouseholdItem).join(RecipeIngredient).where(RecipeIngredient.recipe_id == identifier)).id
    # Foreign ingredient IDs cannot be linked by automatic or explicit choice.
    data = recipe_form(other, ingredient_item=[str(foreign), ''])
    assert other.post('/cooking/new', data=data).status_code == 400


def test_stale_recipe_and_article_conflicts_are_atomic(client, app):
    login(client)
    identifier = create_recipe(client)
    with app.app_context():
        ids = [i.item_id for i in db.session.get(Recipe, identifier).ingredients]
    data = action_form(client, identifier, 'shopping', [str(i) for i in ids])
    with app.app_context():
        db.session.get(HouseholdItem, ids[-1]).stock_status = 'available'
        db.session.commit()
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 409
    with app.app_context():
        assert all(need.quantity == 0 for need in db.session.scalars(select(ShoppingNeed)))
        assert not db.session.scalar(select(CookingAction))
    form = recipe_form(client, version='1')
    assert client.post(f'/cooking/{identifier}/edit', data=form).status_code == 302
    assert client.post(f'/cooking/{identifier}/edit', data=form).status_code == 409


def test_category_rename_order_deactivate_and_delete_used(client, app):
    login(client)
    identifier = create_recipe(client)
    with app.app_context():
        category = db.session.get(Recipe, identifier).category
        category_id, version = category.id, category.version
    data = dict(csrf_token=csrf(client, '/cooking/categories'), category_id=category_id,
        version=version, action='save', name='Hauptgerichte', position='10', active='1')
    assert client.post('/cooking/categories', data=data).status_code == 302
    assert 'Hauptgerichte' in client.get(f'/cooking/{identifier}').get_data(as_text=True)
    data.update(version=2, action='delete')
    assert client.post('/cooking/categories', data=data).status_code == 400
    data.update(action='save', active='')
    assert client.post('/cooking/categories', data=data).status_code == 302
    # Existing recipe may retain an inactive category, new recipes may not select it.
    assert client.post('/cooking/new', data=recipe_form(client, category_id=str(category_id))).status_code == 400


def test_notes_favorites_delete_and_escape(client, app):
    login(client)
    identifier = create_recipe(client, title='<script>Rezept</script>')
    data = action_form(client, identifier, 'note', note='<b>Weniger Zucker</b>')
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 302
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 409
    html = client.get(f'/cooking/{identifier}').get_data(as_text=True)
    assert '&lt;b&gt;Weniger Zucker&lt;/b&gt;' in html
    assert '<script>Rezept</script>' not in html
    data = action_form(client, identifier, 'favorite', favorite='1')
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 302
    assert '&lt;script&gt;Rezept&lt;/script&gt;' in client.get('/cooking?filter=favorites').get_data(as_text=True)
    assert client.post(f'/cooking/{identifier}/action', data=action_form(client, identifier, 'delete')).status_code == 302
    with app.app_context():
        assert db.session.get(Recipe, identifier) is None
        assert not db.session.scalar(select(RecipeNote))
        assert len(db.session.scalars(select(HouseholdItem)).all()) == 2


def test_image_is_sanitized_and_private(client, app):
    login(client)
    image = BytesIO()
    Image.new('RGB', (1600, 800), 'green').save(image, format='PNG')
    image.seek(0)
    data = recipe_form(client)
    data['image'] = (image, 'recipe.png')
    response = client.post('/cooking/new', data=data, content_type='multipart/form-data')
    assert response.status_code == 302
    identifier = int(response.location.split('/')[-1])
    photo = client.get(f'/cooking/{identifier}/image')
    assert photo.mimetype == 'image/jpeg'
    assert photo.headers['Cache-Control'] == 'no-store'
    assert Image.open(BytesIO(photo.data)).size == (1400, 700)
    assert app.test_client().get(f'/cooking/{identifier}/image').status_code == 302
    data = recipe_form(client)
    data['image'] = (BytesIO(b'<svg>bad</svg>'), 'image.svg')
    assert client.post('/cooking/new', data=data, content_type='multipart/form-data').status_code == 400


def test_invalid_quantities_and_no_cross_recipe_batch(client, app):
    login(client)
    for invalid in ['NaN', 'Infinity', '0', '-1', '1.0001']:
        assert client.post('/cooking/new', data=recipe_form(client, servings=invalid)).status_code == 400
    identifier = create_recipe(client)
    item_id, _, _ = seed_item(app)
    data = action_form(client, identifier, 'shopping', [str(item_id)])
    data[f'item_version_{item_id}'] = '1'
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 404


def test_recipe_context_cleared_on_purchase_and_restored_by_undo(client, app):
    from test_app import action
    login(client)
    identifier = create_recipe(client)
    with app.app_context():
        item_id = db.session.get(Recipe, identifier).ingredients[0].item_id
    data = action_form(client, identifier, 'shopping', [str(item_id)])
    assert client.post(f'/cooking/{identifier}/action', data=data).status_code == 302
    with app.app_context():
        item = db.session.get(HouseholdItem, item_id)
        version = item.version
    assert action(client, item_id, 'purchase', version, quantity=1).status_code == 302
    with app.app_context():
        need = db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == item_id))
        assert need.recipe_context == []
        event = db.session.scalar(select(Activity).where(Activity.item_id == item_id).order_by(Activity.id.desc()))
        event_id, version = event.id, event.version_after
    assert client.post(f'/activity/{event_id}/undo', data={'csrf_token': csrf(client, '/'),
        'request_id': str(uuid4()), 'version': version}).status_code == 302
    with app.app_context():
        need = db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == item_id))
        assert need.quantity == 1
        assert need.recipe_context[0]['title'] == 'Quark-Spätzli'
