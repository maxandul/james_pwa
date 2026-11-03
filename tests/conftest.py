import os

import pytest
from sqlalchemy import make_url

from james import create_app
from james.extensions import db
from james.models import Household, Membership, User

PASSWORD = "test-password-12345"


@pytest.fixture
def app(tmp_path):
    url = os.getenv("JAMES_TEST_DATABASE_URL", "sqlite:///" + (tmp_path / "test.sqlite").as_posix())
    if not make_url(url).get_backend_name() == "sqlite" and not (make_url(url).database or "").startswith("james_test_"):
        raise RuntimeError("Tests refuse databases without james_test_ prefix.")
    app = create_app({"TESTING": True, "SECRET_KEY": "test-only-secret-" * 4,
        "SQLALCHEMY_DATABASE_URI": url, "SESSION_COOKIE_SECURE": False,
        "PUBLIC_BASE_URL": "http://localhost"})
    with app.app_context():
        db.create_all()
        home = Household(name="Testhaushalt")
        other = Household(name="Anderer Haushalt")
        db.session.add_all([home, other])
        db.session.flush()
        for name, email, household, role in (
            ("Alex", "owner@example.test", home, "owner"),
            ("Sam", "member@example.test", home, "member"),
            ("Kim", "other@example.test", other, "owner"),
        ):
            user = User(name=name, email=email)
            user.set_password(PASSWORD)
            db.session.add(user)
            db.session.flush()
            db.session.add(Membership(user_id=user.id, household_id=household.id, role=role))
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()
