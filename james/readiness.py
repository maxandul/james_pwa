"""Readiness requires a migrated schema, not merely an accepting DB socket."""
from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from .extensions import db


def database_ready():
    connection = db.session.connection()
    tables = set(inspect(connection).get_table_names())
    if not set(db.metadata.tables).issubset(tables) or "alembic_version" not in tables:
        return False
    versions = set(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
    migrations = ScriptDirectory(str(Path(__file__).resolve().parent.parent / "migrations"))
    return versions == set(migrations.get_heads())
