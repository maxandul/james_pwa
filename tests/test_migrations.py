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
        assert connection.execute("SELECT settings,version FROM household").fetchone() == ("{}",1)
        assert connection.execute("SELECT preferences,version FROM user").fetchone() == ("{}",1)


    migrate("downgrade", "e691ea9e9398")
    migrate("upgrade")
    migrate("check")
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT name,is_favorite,archived FROM household_item").fetchone() == ("Kaffee", 0, 0)
        assert connection.execute("SELECT COUNT(*) FROM activity").fetchone() == (1,)


def test_assortment_migration_backfills_sources_and_preserves_barcodes(tmp_path):
    path = tmp_path / 'assortment.sqlite'
    env = os.environ.copy()
    env.update(APP_ENV='development', SECRET_KEY=secrets.token_hex(32), DATABASE_URL='sqlite:///' + path.as_posix())
    def migrate(*args):
        result = subprocess.run(['python', '-m', 'flask', '--app', 'james', 'db', *args],
            env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
    migrate('upgrade', 'b8cf5f8bfc8c')
    with sqlite3.connect(path) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute("INSERT INTO household (id,name) VALUES (1,'Test')")
        connection.execute("INSERT INTO household_item (id,household_id,name,category,source,unit,default_quantity,stock_status,version) VALUES (1,1,'Milch','Kuehlung','MIGROS','Liter',2,'unknown',1)")
        connection.execute("INSERT INTO shopping_need (id,item_id,quantity) VALUES (1,1,2)")
        connection.execute("INSERT INTO product (id,household_id,item_id,name,brand,package_text,data_source) VALUES (1,1,1,'Testmilch','Test','1 Liter','manual')")
        connection.execute("INSERT INTO product_barcode (household_id,product_id,code,gtin) VALUES (1,1,'4006381333931','04006381333931')")
    migrate('upgrade')
    migrate('check')
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT category,source,version FROM household_item").fetchone() == ('Kuehlung','MIGROS',1)
        assert connection.execute("SELECT name FROM category WHERE name='Kuehlung'").fetchone() == ('Kuehlung',)
        assert connection.execute("SELECT COUNT(*) FROM purchase_source WHERE name_key='migros'").fetchone() == (1,)
        assert connection.execute("SELECT s.name FROM item_source i JOIN purchase_source s ON s.id=i.source_id").fetchone() == ('Migros',)
        assert connection.execute("SELECT version FROM product").fetchone() == (1,)
        assert connection.execute("SELECT code FROM product_barcode").fetchone() == ('4006381333931',)
        assert connection.execute("SELECT quantity FROM shopping_need").fetchone() == (2,)
    migrate('downgrade', 'b8cf5f8bfc8c')
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT code FROM product_barcode").fetchone() == ('4006381333931',)
    migrate('upgrade')
    migrate('check')
