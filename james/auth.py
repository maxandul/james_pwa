import hmac
from datetime import timedelta
from hashlib import sha256

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import case, select
from werkzeug.security import check_password_hash

from .extensions import db
from .models import LoginThrottle, User, utcnow
from .services import accept_invitation, membership_for

auth = Blueprint("auth", __name__)


def login_allowed(email):
    """Durable, atomic limits per email and socket IP; no untrusted proxy headers."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.engine.dialect.name == "postgresql" else sqlite_insert
    now = utcnow()
    until = now + timedelta(minutes=15)
    allowed = True
    for scope, value, limit in (("email", email, 8), ("ip", request.remote_addr or "unknown", 40)):
        key = hmac.new(current_app.secret_key.encode(), f"{scope}:{value}".encode(), sha256).hexdigest()
        stmt = insert(LoginThrottle).values(key=key, failures=1, blocked_until=until)
        expired = LoginThrottle.blocked_until <= now
        stmt = stmt.on_conflict_do_update(index_elements=[LoginThrottle.key], set_={
            "failures": case((expired, 1), else_=LoginThrottle.failures + 1),
            "blocked_until": case((expired, until), else_=LoginThrottle.blocked_until),
        }).returning(LoginThrottle.failures)
        count = db.session.execute(stmt).scalar_one()
        allowed = allowed and count <= limit
    db.session.commit()
    return allowed


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and membership_for(current_user.id):
        return redirect(url_for("main.home"))
    error = None
    status = 200
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()[:254]
        if not login_allowed(email):
            error = "Zu viele Anmeldeversuche. Bitte in 15 Minuten erneut versuchen."
            status = 429
        else:
            user = db.session.scalar(select(User).where(User.email == email))
            password = request.form.get("password", "")[:129]
            valid = check_password_hash(user.password_hash if user else current_app.config["DUMMY_PASSWORD_HASH"], password)
            if valid and user and user.active and membership_for(user.id):
                session.clear()
                session.permanent = True
                login_user(user, fresh=True)
                return redirect(url_for("main.home"))
            error = "E-Mail-Adresse oder Passwort stimmt nicht."
            status = 401
    return render_template("login.html", error=error), status


@auth.post("/logout")
def logout():
    if current_user.is_authenticated:
        from sqlalchemy import update
        from .models import ShopLogin
        db.session.execute(update(ShopLogin).where(ShopLogin.user_id == current_user.id,
            ShopLogin.state.in_(('queued', 'creating', 'running', 'pending', 'submitting', 'accepted')))
            .values(state='cancelled'))
        db.session.commit()
    logout_user()
    session.clear()
    response = redirect(url_for("auth.login"))
    response.headers["Clear-Site-Data"] = '"storage", "cache"'
    return response


@auth.route("/join", methods=["GET", "POST"])
def join():
    if current_user.is_authenticated:
        return render_template("error.html", message="Bitte melde dich zuerst ab, um einen neuen Zugang ueber eine Einladung einzurichten."), 409
    error = None
    if request.method == "POST":
        try:
            accept_invitation(request.form.get("token", ""), request.form.get("email", ""),
                request.form.get("name", ""), request.form.get("password", ""))
            db.session.commit()
            flash("Dein Zugang ist bereit. Du kannst dich jetzt anmelden.", "success")
            return redirect(url_for("auth.login"))
        except ValueError as exc:
            db.session.rollback()
            error = str(exc)
    return render_template("join.html", error=error), (400 if error else 200)
