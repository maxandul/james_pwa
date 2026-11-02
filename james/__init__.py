import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from werkzeug.security import generate_password_hash

from .extensions import csrf, db, login_manager, migrate


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    environment = os.getenv("APP_ENV", "production")
    database_url = os.getenv("DATABASE_URL", "sqlite:///james.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY"), SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5067"),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=environment != "development",
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        MAX_CONTENT_LENGTH=32 * 1024, MAX_FORM_MEMORY_SIZE=32 * 1024,
        MAX_FORM_PARTS=30,
        OPENFOODFACTS_ENVIRONMENT=os.getenv("OPENFOODFACTS_ENVIRONMENT", "staging" if environment == "development" else "production"),
        OPENFOODFACTS_USER_AGENT=os.getenv("OPENFOODFACTS_USER_AGENT", "JamesPWA/0.1 (+https://github.com/maxandul/james_pwa)"),
        JAYJAY_ENABLED=os.getenv('JAYJAY_ENABLED', '') == '1',
        OPENAI_API_KEY=os.getenv('OPENAI_API_KEY', ''),
        OPENAI_MODEL=os.getenv('OPENAI_MODEL', ''),
        SHOP_LOGIN_PILOT_ENABLED=os.getenv('SHOP_LOGIN_PILOT_ENABLED', '') == '1',
        GALAXUS_HOUSEHOLD_ID=os.getenv('GALAXUS_HOUSEHOLD_ID', ''),
        GALAXUS_EMAIL=os.getenv('GALAXUS_EMAIL', ''),
        GALAXUS_PASSWORD=os.getenv('GALAXUS_PASSWORD', ''),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"] or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("SECRET_KEY muss mindestens 32 zufaellige Zeichen enthalten.")
    if app.config["OPENFOODFACTS_ENVIRONMENT"] not in {"staging", "production"}:
        raise RuntimeError("OPENFOODFACTS_ENVIRONMENT muss staging oder production sein.")
    origin = urlsplit(app.config["PUBLIC_BASE_URL"])
    if origin.scheme not in {"http", "https"} or not origin.netloc or origin.path not in {"", "/"} or origin.query or origin.fragment or origin.username:
        raise RuntimeError("PUBLIC_BASE_URL muss ein gueltiger HTTP(S)-Origin sein.")
    if not app.testing and environment != "development":
        if origin.scheme != "https" or not database_url.startswith("postgresql+psycopg://"):
            raise RuntimeError("Produktion braucht HTTPS PUBLIC_BASE_URL und Postgres DATABASE_URL.")
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    @app.before_request
    def receipt_request_limits():
        # Registered before CSRF accesses multipart form data.
        if request.path.startswith("/receipts/"):
            request.max_content_length = 11 * 1024 * 1024 if request.path == "/receipts/new" else 96 * 1024
            # Multipart decoder needs room for a read chunk plus its buffered remainder.
            request.max_form_memory_size = 256 * 1024
            request.max_form_parts = 300
        elif request.path == '/plans' or request.path.startswith('/plans/'):
            request.max_content_length = 256 * 1024
            request.max_form_memory_size = 256 * 1024
            request.max_form_parts = 2500

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Bitte melde dich an."
    migrate.init_app(app, db, compare_type=True)
    app.config["DUMMY_PASSWORD_HASH"] = generate_password_hash("dummy-account-check-only")

    from .models import User

    @login_manager.user_loader
    def load_user(identifier):
        try:
            user_id, version = map(int, identifier.split(":"))
        except (ValueError, AttributeError):
            return None
        user = db.session.get(User, user_id)
        return user if user and user.active and user.auth_version == version else None

    from .auth import auth
    from .views import main
    from .cli import register_cli
    from .scan import scan
    from .pwa import pwa
    from .products import products
    from .receipts import receipts
    from .plans import plans
    from .chat import chat
    from .shop_login import shop_login
    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(scan)
    app.register_blueprint(pwa)
    app.register_blueprint(products)
    app.register_blueprint(receipts)
    app.register_blueprint(plans)
    app.register_blueprint(chat)
    app.register_blueprint(shop_login)
    register_cli(app)
    from .shop_login_worker import register_shop_cli
    register_shop_cli(app)

    @app.after_request
    def response_headers(response):
        response.headers["Content-Security-Policy"] = "default-src 'self'; worker-src 'self'; manifest-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        camera = "(self)" if request.endpoint == "scan.index" else "()"
        response.headers["Permissions-Policy"] = f"camera={camera}, microphone=(), geolocation=()"
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        # No authenticated HTML, invitation links or CSRF tokens in shared caches.
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template("error.html", message="Die Sitzung ist abgelaufen oder die Anfrage ist ungueltig. Bitte die Seite neu laden."), 400

    @app.errorhandler(IntegrityError)
    @app.errorhandler(StaleDataError)
    def conflict_error(error):
        db.session.rollback()
        return render_template("error.html", message="Die Daten wurden inzwischen geaendert. Bitte neu laden und erneut pruefen."), 409

    @app.errorhandler(403)
    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", message="Diese Seite ist nicht verfuegbar."), error.code

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("error.html", message="Das hat gerade nicht geklappt. Bitte versuche es spaeter erneut."), 500

    return app
