import click
from sqlalchemy import select

from .extensions import db
from .models import Household, Membership, User
from .services import clean_email, clean_text, validate_password


def register_cli(app):
    from .coop_pilot import register_coop_cli
    register_coop_cli(app)
    @app.cli.command('jayjay-check')
    def jayjay_check():
        """Verify model access without sending household records or enabling chat."""
        import time
        from .jayjay import responses_request
        if not app.config['OPENAI_API_KEY'] or not app.config['OPENAI_MODEL']:
            raise click.ClickException('OPENAI_API_KEY und OPENAI_MODEL fehlen.')
        try:
            result = responses_request([{'role': 'user', 'content': 'Dies ist ein Verbindungstest. Antworte nur mit Bereit und verwende keine Werkzeuge.'}], time.monotonic() + 20)
            output = result.get('output', [])
            text = any(part.get('type') == 'output_text' and part.get('text') for item in output
                if item.get('type') == 'message' for part in item.get('content', []))
            if result.get('status') != 'completed' or not text or any(item.get('type') == 'function_call' for item in output):
                raise ValueError('Verbindungstest wurde nicht vollständig abgeschlossen.')
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo('OpenAI-Verbindung erfolgreich. Haushaltsdaten wurden nicht übertragen; Chat-Aktivierung bleibt separat.')

    @app.cli.command("init-household")
    @click.option("--email", prompt="E-Mail")
    @click.option("--name", prompt="Dein Name")
    @click.option("--household", prompt="Haushaltsname", default="Unser Zuhause")
    @click.password_option(confirmation_prompt=True)
    def init_household(email, name, household, password):
        """Create the first owner out of band; no public registration."""
        try:
            email = clean_email(email)
            name = clean_text(name, "Name", 80)
            household = clean_text(household, "Haushaltsname", 100)
            validate_password(password)
            if db.session.scalar(select(User.id).limit(1)):
                raise ValueError("Bereits eingerichtet. Weitere Zugänge nur über Einladungen erstellen.")
            home = Household(name=household)
            user = User(email=email, name=name)
            user.set_password(password)
            db.session.add_all([home, user])
            db.session.flush()
            db.session.add(Membership(user_id=user.id, household_id=home.id, role="owner"))
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            raise click.ClickException(str(exc)) from exc
        click.echo("Haushalt und persönlicher Zugang sind eingerichtet.")

    @app.cli.command("reset-password")
    @click.option("--email", prompt="E-Mail")
    @click.password_option(confirmation_prompt=True)
    def reset_password(email, password):
        """Operator-assisted recovery; invalidate all existing sessions."""
        try:
            email = clean_email(email)
            validate_password(password)
            user = db.session.scalar(select(User).where(User.email == email).with_for_update())
            if not user:
                raise ValueError("Zugang nicht gefunden.")
            user.set_password(password)
            user.auth_version += 1
            db.session.commit()
        except ValueError as exc:
            db.session.rollback()
            raise click.ClickException(str(exc)) from exc
        click.echo("Passwort gesetzt; bisherige Sitzungen sind ungültig.")

    @app.cli.command("revoke-member")
    @click.option("--email", prompt="E-Mail")
    @click.confirmation_option(prompt="Diesen persönlichen Zugang sperren?")
    def revoke_member(email):
        """Block a member and their sessions; the only owner cannot be revoked."""
        email = clean_email(email)
        user = db.session.scalar(select(User).where(User.email == email).with_for_update())
        membership = db.session.scalar(select(Membership).where(Membership.user_id == user.id)) if user else None
        if not user or not membership:
            raise click.ClickException("Zugang nicht gefunden.")
        if membership.role == "owner":
            raise click.ClickException("Der Haushaltsverwalter kann hier nicht gesperrt werden.")
        membership.active = False
        user.active = False
        user.auth_version += 1
        db.session.commit()
        click.echo("Zugang gesperrt.")
