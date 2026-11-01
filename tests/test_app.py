import re
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import select

from james import create_app
from james.extensions import db
from james.models import Activity, HouseholdItem, Invitation, Membership, ShoppingNeed, User, utcnow
from james.services import Conflict, accept_invitation, change_item, create_item, make_invitation
from conftest import PASSWORD


def csrf(client, path="/login"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(client, email="owner@example.test"):
    return client.post("/login", data={"csrf_token": csrf(client), "email": email, "password": PASSWORD})


def seed_item(app, email="owner@example.test"):
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == email))
        member = db.session.scalar(select(Membership).where(Membership.user_id == user.id))
        item = create_item(member.household_id, {"name": "Kaffee", "quantity": "2"})
        db.session.commit()
        return item.id, member.household_id, user.id


def action(client, item_id, action_name, version, quantity=None, key=None):
    return client.post(f"/items/{item_id}/action", data={
        "csrf_token": csrf(client, "/"), "action": action_name,
        "version": version, "quantity": quantity, "request_id": key or str(uuid4()),
    })


def test_config_refuses_missing_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app()


def test_production_requires_postgres_and_https(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "s" * 48)
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    with pytest.raises(RuntimeError, match="Produktion"):
        create_app()


def test_no_public_registration_and_login_is_required(client):
    assert client.get("/").status_code == 302
    assert client.get("/shopping").status_code == 302
    assert client.get("/register").status_code == 404


def test_login_logout_and_headers(client):
    assert login(client).status_code == 302
    response = client.get("/")
    assert response.status_code == 200
    assert "Was braucht ihr?" in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert client.get("/logout").status_code == 405
    assert client.post("/logout", data={"csrf_token": csrf(client, "/")}).status_code == 302
    assert client.get("/").status_code == 302


def test_csrf_required_for_login_and_mutation(client):
    assert client.post("/login", data={"email": "owner@example.test", "password": PASSWORD}).status_code == 400
    login(client)
    assert client.post("/items/new", data={"name": "Kaffee"}).status_code == 400


def test_login_generic_failure_and_throttle(client):
    for attempt in range(8):
        response = client.post("/login", data={"csrf_token": csrf(client), "email": "missing@example.test", "password": "wrong"})
        assert response.status_code == 401
        assert "E-Mail-Adresse oder Passwort stimmt nicht" in response.text
    assert client.post("/login", data={"csrf_token": csrf(client), "email": "missing@example.test", "password": "wrong"}).status_code == 429


def test_revoked_membership_blocks_existing_session(app, client):
    login(client, "member@example.test")
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "member@example.test"))
        db.session.scalar(select(Membership).where(Membership.user_id == user.id)).active = False
        db.session.commit()
    assert client.get("/").status_code == 403


def test_password_recovery_invalidates_sessions(app, client):
    login(client)
    result = app.test_cli_runner().invoke(args=["reset-password", "--email", "owner@example.test"], input="replacement-password-123\nreplacement-password-123\n")
    assert result.exit_code == 0, result.output
    assert client.get("/").status_code == 302
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == "owner@example.test"))
        assert user.check_password("replacement-password-123")
        assert user.password_hash != "replacement-password-123"


def test_invite_fragment_email_binding_and_one_use(app, client):
    login(client)
    response = client.post("/household", data={"csrf_token": csrf(client, "/household"), "email": "new@example.test"})
    assert response.status_code == 200
    token = re.search(r'http://localhost/join#([A-Za-z0-9_-]+)', response.text).group(1)
    assert response.headers["Cache-Control"] == "no-store"
    with app.app_context():
        invitation = db.session.scalar(select(Invitation))
        assert invitation.token_hash == sha256(token.encode()).hexdigest()
        assert invitation.token_hash != token
    newcomer = app.test_client()
    payload = {"csrf_token": csrf(newcomer, "/join"), "token": token, "email": "wrong@example.test", "name": "Pat", "password": PASSWORD}
    assert newcomer.post("/join", data=payload).status_code == 400
    payload["email"] = "NEW@example.test"
    assert newcomer.post("/join", data=payload).status_code == 302
    assert newcomer.post("/join", data=payload).status_code == 400
    assert login(newcomer, "new@example.test").status_code == 302
    assert "Testhaushalt" in newcomer.get("/").text


@pytest.mark.parametrize("invalid", ["expired", "revoked", "issuer_revoked"])
def test_invalid_invites_rejected(app, invalid):
    with app.app_context():
        member = db.session.scalar(select(Membership).where(Membership.role == "owner"))
        invitation, token = make_invitation(member, "new@example.test")
        if invalid == "expired":
            invitation.expires_at = utcnow() - timedelta(seconds=1)
        elif invalid == "revoked":
            invitation.revoked_at = utcnow()
        else:
            member.active = False
        db.session.commit()
        with pytest.raises(ValueError):
            accept_invitation(token, "new@example.test", "Pat", PASSWORD)


def test_reissued_invitation_invalidates_old(app):
    with app.app_context():
        member = db.session.scalar(select(Membership).where(Membership.role == "owner"))
        old, token = make_invitation(member, "new@example.test")
        db.session.commit()
        make_invitation(member, "new@example.test")
        db.session.commit()
        with pytest.raises(ValueError):
            accept_invitation(token, "new@example.test", "Pat", PASSWORD)


def test_members_cannot_manage_invites_or_access_other_households(app, client):
    item_id, _, _ = seed_item(app, "other@example.test")
    login(client, "member@example.test")
    assert client.get("/household").status_code == 403
    assert action(client, item_id, "replenish", 1).status_code == 404
    assert f'/items/{item_id}/action' not in client.get("/").text


def test_two_members_share_list(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    assert action(client, item_id, "replenish", 1).status_code == 302
    second = app.test_client()
    login(second, "member@example.test")
    assert "Kaffee" in second.get("/shopping").text


def test_create_item_validates_and_escapes(client):
    login(client)
    response = client.post("/items/new", data={"csrf_token": csrf(client, "/items/new"), "name": "<script>alert(1)</script>", "quantity": "1"})
    assert response.status_code == 302
    assert "&lt;script&gt;" in client.get("/").text
    assert "<script>alert(1)</script>" not in client.get("/").text
    response = client.post("/items/new", data={"csrf_token": csrf(client, "/items/new"), "name": "Pasta", "quantity": "0"})
    assert response.status_code == 400


def test_replenish_deduplicates_and_request_retry_is_idempotent(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    key = str(uuid4())
    assert action(client, item_id, "replenish", 1, key=key).status_code == 302
    assert action(client, item_id, "replenish", 1, key=key).status_code == 302
    assert action(client, item_id, "replenish", 2).status_code == 302
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2
        assert len(db.session.scalars(select(Activity)).all()) == 2


def test_stale_additional_quantity_is_rejected(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    action(client, item_id, "replenish", 1)
    assert action(client, item_id, "extra", 1, quantity="1").status_code == 409
    assert action(client, item_id, "extra", 2, quantity="3").status_code == 302
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 5


def test_partial_purchase_retry_and_undo(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    action(client, item_id, "empty", 1)
    key = str(uuid4())
    response = action(client, item_id, "purchase", 2, quantity="1", key=key)
    assert response.status_code == 302
    assert action(client, item_id, "purchase", 2, quantity="1", key=key).status_code == 302
    event_id = int(re.search(r"undo=(\d+)", response.location).group(1))
    assert client.get(response.location).status_code == 200
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 1
        assert db.session.get(HouseholdItem, item_id).stock_status == "available"
    result = client.post(f"/activity/{event_id}/undo", data={"csrf_token": csrf(client, "/"), "request_id": str(uuid4()), "version": 3})
    assert result.status_code == 302
    with app.app_context():
        assert db.session.scalar(select(ShoppingNeed.quantity)) == 2
        assert db.session.get(HouseholdItem, item_id).stock_status == "empty"


def test_purchase_cannot_overfill_or_repeat_new_request(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    action(client, item_id, "replenish", 1)
    assert action(client, item_id, "purchase", 2, quantity="3").status_code == 409
    assert action(client, item_id, "purchase", 2, quantity="2").status_code == 302
    assert action(client, item_id, "purchase", 3, quantity="2").status_code == 409
    assert "Alles erledigt" in client.get("/shopping").text


def test_old_undo_cannot_overwrite_later_change(app):
    item_id, home, user = seed_item(app)
    with app.app_context():
        first = change_item(home, user, item_id, "replenish", str(uuid4()), 1)
        db.session.commit()
        first_id = first.id
        change_item(home, user, item_id, "extra", str(uuid4()), 2, quantity="1")
        db.session.commit()
        with pytest.raises(Conflict):
            change_item(home, user, item_id, "undo", str(uuid4()), 3, activity_id=first_id)


def test_missing_or_reused_request_id_rejected(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    assert action(client, item_id, "empty", 1, key="invalid").status_code == 400
    key = str(uuid4())
    action(client, item_id, "replenish", 1, key=key)
    assert action(client, item_id, "purchase", 2, quantity="1", key=key).status_code == 409


def test_health_is_minimal_and_works(client):
    assert client.get("/health").json == {"status": "ok"}


def test_undo_only_shown_on_direct_action_confirmation(app, client):
    item_id, _, _ = seed_item(app)
    login(client)
    response = action(client, item_id, "replenish", 1)
    event_id = int(re.search(r"undo=(\d+)", response.location).group(1))
    undo_action = f'/activity/{event_id}/undo'
    assert undo_action in client.get(response.location).text
    assert undo_action not in client.get("/shopping").text
    assert undo_action not in client.get("/").text
