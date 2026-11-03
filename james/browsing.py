"""Bounded, household-scoped article browsing without hydrating the full catalogue."""
from sqlalchemy import case, event, func, or_, select

from .extensions import db
from .models import HouseholdItem, ItemSource, Product, PurchaseSource, ShoppingNeed, ShopOffer

PAGE_SIZE = 48


def configure_search(app):
    # SQLite's built-in lower() handles ASCII only. Keep local/test Unicode search
    # consistent with Postgres Unicode folding, without a schema migration.
    with app.app_context():
        engine = db.engine
        if engine.dialect.name == 'sqlite':
            @event.listens_for(engine, 'connect')
            def sqlite_casefold(connection, record):
                connection.create_function('james_casefold', 1,
                    lambda value: value.casefold() if value is not None else None,
                    deterministic=True)


def source_match(household_id, name):
    linked = select(ItemSource.item_id).join(PurchaseSource).where(
        ItemSource.item_id == HouseholdItem.id, PurchaseSource.household_id == household_id,
        PurchaseSource.name == name).exists()
    offered = select(Product.id).join(ShopOffer).join(PurchaseSource).where(
        Product.item_id == HouseholdItem.id, Product.household_id == household_id,
        ShopOffer.household_id == household_id, ShopOffer.active.is_(True),
        PurchaseSource.household_id == household_id, PurchaseSource.name == name).exists()
    return or_(HouseholdItem.source == name, linked, offered)


def browse(household_id, context):
    archived = context['view'] == 'archived'
    scope = (HouseholdItem.household_id == household_id, HouseholdItem.archived.is_(archived))
    predicates = list(scope)
    if context['view'] == 'favorites':
        predicates.append(HouseholdItem.is_favorite.is_(True))
    if context.get('q'):
        folded = func.james_casefold(HouseholdItem.name) if db.engine.dialect.name == 'sqlite' else func.casefold(
            HouseholdItem.name.collate('pg_unicode_fast'))
        predicates.append(folded.contains(context['q'].casefold(), autoescape=True))
    if context.get('filter_category'):
        predicates.append(HouseholdItem.category == context['filter_category'])
    if context.get('filter_source'):
        predicates.append(source_match(household_id, context['filter_source']))
    if context.get('filter_stock'):
        predicates.append(HouseholdItem.stock_status == context['filter_stock'])

    base = select(HouseholdItem, ShoppingNeed).join(ShoppingNeed).where(*predicates)
    total = db.session.scalar(select(func.count()).select_from(base.subquery()))
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(context.get('page', 1), pages)
    rows = db.session.execute(base.order_by(HouseholdItem.is_favorite.desc(),
        HouseholdItem.name, HouseholdItem.id).limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE)).all()
    pending, active_count = db.session.execute(select(
        func.coalesce(func.sum(case((ShoppingNeed.quantity > 0, 1), else_=0)), 0),
        func.count(HouseholdItem.id)).join(ShoppingNeed).where(
            HouseholdItem.household_id == household_id, HouseholdItem.archived.is_(False))).one()

    # Facets describe the entire selected archive scope, not just the current page
    # or matching rows, so another applied filter never removes the escape route.
    categories = db.session.scalars(select(HouseholdItem.category).where(*scope).distinct().order_by(HouseholdItem.category)).all()
    preferred = select(HouseholdItem.source).where(*scope)
    linked = select(PurchaseSource.name).join(ItemSource).join(HouseholdItem,
        ItemSource.item_id == HouseholdItem.id).where(*scope, PurchaseSource.household_id == household_id)
    offered = select(PurchaseSource.name).join(ShopOffer).join(Product).join(HouseholdItem,
        Product.item_id == HouseholdItem.id).where(*scope, Product.household_id == household_id,
            ShopOffer.household_id == household_id, ShopOffer.active.is_(True), PurchaseSource.household_id == household_id)
    sources = sorted(db.session.scalars(preferred.union(linked, offered)).all())
    return dict(rows=rows, pending=pending, active_count=active_count, total=total,
        page=page, pages=pages, first=(page - 1) * PAGE_SIZE + 1 if total else 0,
        last=min(page * PAGE_SIZE, total), browse_categories=categories, browse_sources=sources)
