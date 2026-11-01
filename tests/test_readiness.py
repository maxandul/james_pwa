from pathlib import Path

from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import text

from james.extensions import db
from james.models import ProductBarcode


@pytest.fixture(autouse=True)
def remove_test_revision(app):
    yield
    with app.app_context():
        db.session.execute(text("DROP TABLE IF EXISTS alembic_version"))
        db.session.commit()


def stamp_test_schema(app, revision=None):
    """Fixtures use create_all; stamp only this isolated test schema."""
    with app.app_context():
        if revision is None:
            revision = ScriptDirectory(str(Path(__file__).resolve().parents[1] / "migrations")).get_current_head()
        db.session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
        db.session.execute(text("INSERT INTO alembic_version (version_num) VALUES (:revision)"), {"revision": revision})
        db.session.commit()


def test_reachable_but_unmigrated_database_is_not_ready(client):
    assert client.get("/health").status_code == 503
    assert client.get("/health").json == {"status": "unavailable"}


def test_current_complete_schema_is_ready(app, client):
    stamp_test_schema(app)
    assert client.get("/health").status_code == 200
    assert client.get("/health").json == {"status": "ok"}


def test_old_revision_is_not_ready_even_with_tables(app, client):
    stamp_test_schema(app, "eebb352b7301")
    assert client.get("/health").status_code == 503


def test_missing_table_is_not_ready_even_when_stamped_current(app, client):
    stamp_test_schema(app)
    with app.app_context():
        ProductBarcode.__table__.drop(db.engine)
    assert client.get("/health").status_code == 503
