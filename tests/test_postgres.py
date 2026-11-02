from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select

from james.extensions import db
from james.models import CatalogGate, HouseholdItem, Invitation, Membership, Product, ProductBarcode, ShoppingNeed
from james.barcodes import register_barcode
from james.catalog import CatalogUnavailable, reserve_catalog_lookup
from james.services import Conflict, change_item, create_item, make_invitation


def test_concurrent_replenish_and_purchase(app):
    with app.app_context():
        if db.engine.dialect.name != "postgresql":
            pytest.skip("Row locking is exercised against the isolated Postgres test database.")
        member = db.session.scalar(select(Membership).where(Membership.role == "owner"))
        item = create_item(member.household_id, {"name": "Pasta", "quantity": "2"})
        db.session.commit()
        home, user, item_id = member.household_id, member.user_id, item.id
    barrier = Barrier(2)
    def mutate(action, version, quantity=None):
        with app.app_context():
            barrier.wait(timeout=10)
            try:
                change_item(home, user, item_id, action, str(uuid4()), version, quantity=quantity)
                db.session.commit()
                return "ok"
            except Conflict:
                db.session.rollback()
                return "conflict"
            finally:
                db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: mutate("replenish", 1), range(2)))
    assert sorted(results) == ["conflict", "ok"]
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity).where(ShoppingNeed.item_id == item_id)) == 2
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: mutate("purchase", 2, "2"), range(2)))
    assert sorted(results) == ["conflict", "ok"]
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity).where(ShoppingNeed.item_id == item_id)) == 0


def test_concurrent_invitation_issuance_keeps_one_active_link(app):
    with app.app_context():
        if db.engine.dialect.name != "postgresql":
            pytest.skip("Invitation issuance locking requires isolated Postgres.")
        owner_id = db.session.scalar(select(Membership.id).where(Membership.role == "owner"))
    barrier = Barrier(2)
    def issue(_):
        with app.app_context():
            member = db.session.get(Membership, owner_id)
            barrier.wait(timeout=10)
            make_invitation(member, "new@example.test")
            db.session.commit()
            db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(issue, range(2)))
    with app.app_context():
        invitations = db.session.scalars(select(Invitation)).all()
        assert len(invitations) == 2
        assert sum(invitation.revoked_at is None for invitation in invitations) == 1


def test_concurrent_archive_and_replenish_cannot_hide_open_need(app):
    with app.app_context():
        if db.engine.dialect.name != "postgresql":
            pytest.skip("Archive/replenish race requires isolated Postgres.")
        member = db.session.scalar(select(Membership).where(Membership.role == "owner"))
        item = create_item(member.household_id, {"name": "Pasta"})
        db.session.commit()
        home, user, item_id = member.household_id, member.user_id, item.id
    barrier = Barrier(2)
    def mutate(action):
        with app.app_context():
            barrier.wait(timeout=10)
            try:
                change_item(home, user, item_id, action, str(uuid4()), 1)
                db.session.commit()
                return "ok"
            except Conflict:
                db.session.rollback()
                return "conflict"
            finally:
                db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(mutate, ["archive", "replenish"]))
    assert sorted(results) == ["conflict", "ok"]
    with app.app_context():
        item = db.session.get(HouseholdItem, item_id)
        need = db.session.scalar(select(ShoppingNeed).where(ShoppingNeed.item_id == item_id))
        assert not (item.archived and need.quantity)


def test_concurrent_barcode_registration_creates_one_article(app):
    with app.app_context():
        if db.engine.dialect.name != "postgresql":
            pytest.skip("Concurrent first registration requires Postgres.")
        home = db.session.scalar(select(Membership.household_id).where(Membership.role == "owner"))
    barrier = Barrier(2)
    def register(_):
        with app.app_context():
            barrier.wait(timeout=10)
            barcode, created = register_barcode(home, {"code": "4006381333931", "product_name": "Testprodukt", "item_id": "new"})
            db.session.commit()
            db.session.remove()
            return created
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(register, range(2)))
    assert sorted(results) == [False, True]
    with app.app_context():
        assert len(db.session.scalars(select(HouseholdItem)).all()) == 1
        assert len(db.session.scalars(select(Product)).all()) == 1
        assert len(db.session.scalars(select(ProductBarcode)).all()) == 1


def test_catalog_gate_is_shared_across_workers(app):
    with app.app_context():
        if db.engine.dialect.name != "postgresql":
            pytest.skip("Cross-worker catalogue gate requires Postgres.")
    barrier = Barrier(2)
    def reserve(_):
        with app.app_context():
            barrier.wait(timeout=10)
            try:
                reserve_catalog_lookup()
                db.session.commit()
                return "reserved"
            except CatalogUnavailable:
                db.session.rollback()
                return "limited"
            finally:
                db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, range(2)))
    assert sorted(results) == ["limited", "reserved"]


def test_simultaneous_shop_preferences_leave_one_choice(app):
    from james.assortment import save_offer, save_product
    from james.models import PurchaseSource, ShopOffer
    with app.app_context():
        if db.engine.dialect.name != "postgresql":
            pytest.skip("Concurrent preference selection requires Postgres.")
        home = db.session.scalar(select(Membership.household_id).where(Membership.role == "owner"))
        item = create_item(home, {"name": "Milch"})
        first = save_product(home, item.id, {"product_name": "A"})
        second = save_product(home, item.id, {"product_name": "B"})
        coop = db.session.scalar(select(PurchaseSource.id).where(PurchaseSource.household_id == home, PurchaseSource.name == "Coop"))
        db.session.commit()
        item_id, product_ids = item.id, [first.id, second.id]
    barrier = Barrier(2)
    def prefer(product_id):
        with app.app_context():
            barrier.wait(timeout=10)
            save_offer(home, item_id, product_id, {"source_id": coop, "units_per_pack": "1", "preferred": "1"})
            db.session.commit()
            db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(prefer, product_ids))
    with app.app_context():
        offers = db.session.scalars(select(ShopOffer).where(ShopOffer.source_id == coop)).all()
        assert len(offers) == 2 and sum(offer.preferred for offer in offers) == 1


def test_simultaneous_receipt_confirmation_books_only_once(app):
    from james.models import Activity, ReceiptImport
    from james.receipts import confirm_receipt, create_draft, serializer
    with app.app_context():
        if db.engine.dialect.name != 'postgresql':
            pytest.skip('Concurrent receipt confirmation requires Postgres.')
        member = db.session.scalar(select(Membership).where(Membership.role == 'owner'))
        home, user_id = member.household_id, member.user_id
        item = create_item(home, {'name': 'Milch'})
        receipt = create_draft(home, 'Milch 1.80', 'f' * 64)
        db.session.commit()
        receipt_id, item_id = receipt.id, item.id
        token = serializer().dumps({'receipt': receipt_id, 'household': home,
            'versions': {str(item_id): item.version}})
    barrier = Barrier(2)
    def confirm(_):
        with app.app_context():
            barrier.wait(timeout=10)
            confirm_receipt(home, user_id, receipt_id, {'review_token': token,
                'target_0': str(item_id), 'quantity_0': '2'})
            db.session.commit()
            db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(confirm, range(2)))
    with app.app_context():
        assert len(db.session.scalars(select(Activity).where(Activity.action == 'receipt')).all()) == 1
        assert db.session.get(ReceiptImport, receipt_id).state == 'confirmed'
