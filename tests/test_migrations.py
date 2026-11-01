import os
import secrets
import subprocess
import sqlite3


def test_migration_upgrade_downgrade_and_metadata(tmp_path):
    env = os.environ.copy()
    env.update(APP_ENV="development", SECRET_KEY=secrets.token_hex(32),
        DATABASE_URL="sqlite:///" + (tmp_path / "migration.sqlite").as_posix())
    for command in (("upgrade",), ("check",), ("downgrade", "base"), ("upgrade",)):
        result = subprocess.run(["python", "-m", "flask", "--app", "james", "db", *command],
            env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr


def test_article_migration_preserves_existing_rows_and_history(tmp_path):
    path = tmp_path / "existing.sqlite"
    env = os.environ.copy()
    env.update(APP_ENV="development", SECRET_KEY=secrets.token_hex(32), DATABASE_URL="sqlite:///" + path.as_posix())
    def migrate(*command):
        result = subprocess.run(["python", "-m", "flask", "--app", "james", "db", *command],
            env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
    migrate("upgrade", "e691ea9e9398")
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("INSERT INTO household (id,name) VALUES (1,'Test')")
        connection.execute("INSERT INTO user (id,email,name,password_hash,auth_version,active) VALUES (1,'test@example.test','Test','test-only-unused',1,1)")
        connection.execute("INSERT INTO household_item (id,household_id,name,category,source,unit,default_quantity,stock_status,version) VALUES (1,1,'Kaffee','Vorrat','Coop','Packung',2,'low',1)")
        connection.execute("INSERT INTO shopping_need (id,item_id,quantity) VALUES (1,1,2)")
        connection.execute("INSERT INTO activity (household_id,item_id,user_id,request_id,action,before_state,after_state,version_after,created_at) VALUES (1,1,1,'legacy-test-request','replenish','{}','{}',1,'2026-11-01 00:00:00')")
    migrate("upgrade")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT name,is_favorite,archived FROM household_item").fetchone() == ("Kaffee", 0, 0)
        assert connection.execute("SELECT quantity FROM shopping_need").fetchone() == (2,)
        assert connection.execute("SELECT COUNT(*) FROM activity").fetchone() == (1,)
    migrate("downgrade", "e691ea9e9398")
    migrate("upgrade")
    migrate("check")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT name,is_favorite,archived FROM household_item").fetchone() == ("Kaffee", 0, 0)
        assert connection.execute("SELECT COUNT(*) FROM activity").fetchone() == (1,)
