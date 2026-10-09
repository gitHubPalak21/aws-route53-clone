"""Registration uses the existing session and owner-scoped resource contracts."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings
from app.core.security import hash_session_token, verify_password
from app.db.database import enable_sqlite_foreign_keys
from app.models import Session, User
from app.services import auth_service
from test_auth import (  # noqa: F401
    LOGIN, anyio_backend, application, client, demo_user, isolated_app,
    parsed_cookie, session_count, settings,
)

pytestmark = pytest.mark.anyio
SIGNUP = {"display_name": "  New User  ", "email": "  New@Example.COM  ", "password": "signup-password123"}


async def test_register_normalizes_hashes_and_authenticates(client: httpx.AsyncClient, db: DBSession) -> None:
    response = await client.post("/api/auth/register", json=SIGNUP)
    assert response.status_code == 201
    user = db.scalar(select(User).where(User.email == "new@example.com"))
    assert user and user.display_name == "New User" and user.is_active
    assert user.password_hash.startswith("$argon2id$") and user.password_hash != SIGNUP["password"]
    assert verify_password(SIGNUP["password"], user.password_hash)
    assert response.json() == {"user": {"id": user.id, "email": "new@example.com", "display_name": "New User"}}
    assert all(value not in response.text for value in [SIGNUP["password"], user.password_hash, "token_hash", "raw_token"])
    cookie = parsed_cookie(response)
    assert cookie["httponly"] and cookie["samesite"] == "lax" and cookie["path"] == "/"
    assert not cookie["secure"] and cookie["max-age"] == "86400" and cookie["expires"] and not cookie["domain"]
    saved = db.scalar(select(Session).where(Session.user_id == user.id))
    assert saved and saved.token_hash == hash_session_token(cookie.value) and saved.token_hash != cookie.value
    assert cookie.value not in response.text and saved.token_hash not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert (await client.get("/api/auth/me")).json() == response.json()
    assert (await client.get("/api/hosted-zones")).json()["total"] == 0


@pytest.mark.parametrize("email", ["new@example.com", " NEW@EXAMPLE.COM "])
async def test_duplicate_email(client: httpx.AsyncClient, db: DBSession, email: str) -> None:
    assert (await client.post("/api/auth/register", json=SIGNUP)).status_code == 201
    response = await client.post("/api/auth/register", json={**SIGNUP, "email": email})
    assert response.status_code == 409 and response.json()["detail"] == "An account with this email already exists."
    assert "set-cookie" not in response.headers and session_count(db) == 1
    assert db.scalar(select(func.count()).select_from(User).where(User.email == "new@example.com")) == 1


@pytest.mark.parametrize("changes", [
    {"display_name": ""}, {"display_name": "  "}, {"display_name": "x" * 129},
    {"email": ""}, {"email": "bad-email"}, {"email": "bad@@example.com"},
    {"password": "1234567"}, {"password": "x" * 1025}, {"password": ""},
])
async def test_invalid_registration_is_safe(client: httpx.AsyncClient, db: DBSession, changes: dict) -> None:
    response = await client.post("/api/auth/register", json={**SIGNUP, **changes})
    assert response.status_code == 422 and "set-cookie" not in response.headers
    assert all(set(issue) == {"type", "loc", "msg"} for issue in response.json()["detail"])
    assert SIGNUP["password"] not in response.text and session_count(db) == 0
    assert db.scalar(select(func.count()).select_from(User)) == 1  # Only the preserved demo seed.


async def test_missing_registration_fields(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/auth/register", json={})).status_code == 422


async def test_race_is_caught_by_unique_constraint(client: httpx.AsyncClient, db: DBSession, monkeypatch: pytest.MonkeyPatch) -> None:
    assert (await client.post("/api/auth/register", json=SIGNUP)).status_code == 201
    # Simulate a stale pre-check; the real SQLite unique constraint must still win.
    original = DBSession.scalar
    calls = 0
    def stale_check(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return None if calls == 1 else original(self, *args, **kwargs)
    monkeypatch.setattr(DBSession, "scalar", stale_check)
    response = await client.post("/api/auth/register", json=SIGNUP)
    assert response.status_code == 409 and session_count(db) == 1
    assert db.scalar(select(func.count()).select_from(User)) == 2


def test_session_failure_rolls_back_user_and_rotation(db: DBSession, settings: Settings, demo_user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    old = auth_service.login(db, settings, LOGIN["email"], LOGIN["password"])
    original = auth_service.create_session_for_user
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("Simulated session failure")
    monkeypatch.setattr(auth_service, "create_session_for_user", fail)
    with pytest.raises(RuntimeError, match="Simulated"):
        auth_service.register(db, settings, "New", "new@example.com", SIGNUP["password"], old.raw_token)
    assert db.scalar(select(User).where(User.email == "new@example.com")) is None
    assert session_count(db) == 1 and auth_service.resolve_session(db, old.raw_token) is not None


async def test_registered_session_survives_reconnect_and_logout(client: httpx.AsyncClient, db_engine: Engine, settings: Settings) -> None:
    registered = await client.post("/api/auth/register", json=SIGNUP)
    token = client.cookies.get("route53_session")
    engine = create_engine(db_engine.url)
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    try:
        app = isolated_app(engine, settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as fresh:
            fresh.cookies.set("route53_session", token)
            assert (await fresh.get("/api/auth/me")).json() == registered.json()
            assert (await fresh.post("/api/auth/logout")).status_code == 200
            assert (await fresh.get("/api/auth/me", headers={"Cookie": f"route53_session={token}"})).status_code == 401
            assert (await fresh.post("/api/auth/login", json={"email": "new@example.com", "password": SIGNUP["password"]})).status_code == 200
    finally:
        engine.dispose()


async def test_registration_uses_production_cookie_config(application: FastAPI, settings: Settings) -> None:
    settings.session_cookie_secure = True
    settings.session_cookie_name = "custom_session"
    settings.session_ttl_hours = 2
    async with httpx.AsyncClient(transport=httpx.ASGITransport(application), base_url="https://test") as secure:
        response = await secure.post("/api/auth/register", json=SIGNUP)
        cookie = parsed_cookie(response, "custom_session")
        assert cookie["secure"] and cookie["httponly"] and cookie["max-age"] == "7200" and cookie["samesite"] == "lax"
        assert (await secure.get("/api/auth/me")).status_code == 200


async def test_register_rejects_untrusted_origin(client: httpx.AsyncClient, db: DBSession) -> None:
    response = await client.post("/api/auth/register", json=SIGNUP, headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 403 and session_count(db) == 0
    assert db.scalar(select(func.count()).select_from(User)) == 1


async def test_registration_rotates_previous_session(client: httpx.AsyncClient, db: DBSession) -> None:
    await client.post("/api/auth/login", json=LOGIN)
    token = client.cookies.get("route53_session")
    registered = await client.post("/api/auth/register", json=SIGNUP)
    assert registered.status_code == 201 and session_count(db) == 1
    assert client.cookies.get("route53_session") != token
    assert (await client.get("/api/auth/me")).json() == registered.json()
    assert (await client.get("/api/auth/me", headers={"Cookie": f"route53_session={token}"})).status_code == 401


async def test_registered_account_cannot_access_other_owners_resources(client: httpx.AsyncClient, application: FastAPI) -> None:
    await client.post("/api/auth/login", json=LOGIN)
    zone = (await client.post("/api/hosted-zones", json={"name": "admin.example.com"})).json()
    records = (await client.get(f"/api/hosted-zones/{zone['id']}/records")).json()["items"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(application), base_url="http://test") as new:
        assert (await new.post("/api/auth/register", json=SIGNUP)).status_code == 201
        assert (await new.get("/api/hosted-zones")).json()["total"] == 0
        base = f"/api/hosted-zones/{zone['id']}"
        attempts = [("GET", base, None), ("PATCH", base, {"comment": "stolen"}), ("DELETE", base, None),
                    ("GET", base + "/records", None), ("POST", base + "/records", {"name": "www", "record_type": "A", "values": ["192.0.2.1"]})]
        record_path = base + "/records/" + records[0]["id"]
        attempts += [("GET", record_path, None), ("PATCH", record_path, {"ttl": 600}), ("DELETE", record_path, None)]
        for method, path, payload in attempts:
            assert (await new.request(method, path, json=payload)).status_code == 404
        own = (await new.post("/api/hosted-zones", json={"name": "new.example.com"})).json()
        assert own["record_count"] == 2
        assert (await client.get(f"/api/hosted-zones/{own['id']}")).status_code == 404
        assert (await client.get("/api/hosted-zones")).json()["total"] == 1


async def test_registration_is_documented(client: httpx.AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    for path, method in [("register", "post"), ("login", "post"), ("me", "get"), ("logout", "post")]:
        assert schema["paths"]["/api/auth/" + path][method]["tags"] == ["Authentication"]
    password = schema["components"]["schemas"]["RegisterRequest"]["properties"]["password"]
    assert password["writeOnly"] and password["minLength"] == 8
    assert not any(field in str(schema) for field in ["password_hash", "token_hash", "raw_token"])
