import os
import secrets
import subprocess


def test_migration_upgrade_downgrade_and_metadata(tmp_path):
    env = os.environ.copy()
    env.update(APP_ENV="development", SECRET_KEY=secrets.token_hex(32),
        DATABASE_URL="sqlite:///" + (tmp_path / "migration.sqlite").as_posix())
    for command in (("upgrade",), ("check",), ("downgrade", "base"), ("upgrade",)):
        result = subprocess.run(["python", "-m", "flask", "--app", "james", "db", *command],
            env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
