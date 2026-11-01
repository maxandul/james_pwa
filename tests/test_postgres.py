from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import select

from james.extensions import db
from james.models import Invitation, Membership, ShoppingNeed
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
