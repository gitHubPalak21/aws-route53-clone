from collections.abc import AsyncIterator, Iterator
from datetime import timedelta
from http.cookies import SimpleCookie

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings, get_settings
from app.core.security import generate_session_token, hash_session_token, verify_password
from app.db.database import enable_sqlite_foreign_keys
from app.db.types import utc_now
from app.dependencies.auth import CurrentUser
from app.dependencies.database import get_db
from app.main import create_app
from app.models import Session, User
from app.scripts.seed_demo_user import seed_demo_user

pytestmark = pytest.mark.anyio
LOGIN = {"email": "admin@route53.local", "password": "admin123"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    get_settings.cache_clear()
    yield Settings(
        _env_file=None, app_env="development", frontend_origin="http://localhost:3000",
        demo_user_email=LOGIN["email"], demo_user_password=LOGIN["password"],
        demo_user_display_name="Admin User", session_cookie_name="route53_session",
        session_ttl_hours=24, session_cookie_secure=False,
    )
    get_settings.cache_clear()


@pytest.fixture
def demo_user(db: DBSession, settings: Settings) -> User:
    return seed_demo_user(db, settings)[0]


def isolated_app(engine: Engine, settings: Settings) -> FastAPI:
    application = create_app()

    def test_db() -> Iterator[DBSession]:
        with DBSession(engine, autoflush=False, expire_on_commit=False) as session:
            yield session

    application.dependency_overrides[get_db] = test_db
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest.fixture
def application(db_engine: Engine, settings: Settings, demo_user: User) -> FastAPI:
    return isolated_app(db_engine, settings)


@pytest.fixture
async def client(application: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(application), base_url="http://test") as test_client:
        yield test_client


def parsed_cookie(response: httpx.Response, name: str = "route53_session"):
    cookies = SimpleCookie()
    cookies.load(response.headers["set-cookie"])
    return cookies[name]


def session_count(db: DBSession) -> int:
    return db.scalar(select(func.count()).select_from(Session)) or 0


def test_seed_hashes_password_and_is_idempotent(db: DBSession, settings: Settings) -> None:
    first, created = seed_demo_user(db, settings)
    password_hash = first.password_hash
    assert created
    assert password_hash != LOGIN["password"]
    assert password_hash.startswith("$argon2id$")
    assert verify_password(LOGIN["password"], password_hash)
    assert not verify_password("incorrect", password_hash)
    first.is_active = False
    db.commit()
    changed_settings = settings.model_copy(update={
        "demo_user_password": SecretStr("a changed password"), "demo_user_display_name": "Changed name",
    })
    second, created = seed_demo_user(db, changed_settings)
    assert not created and second.id == first.id
    assert second.password_hash == password_hash
    assert second.display_name == "Admin User" and not second.is_active
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_configured_seed_normalizes_email(db: DBSession) -> None:
    configured = Settings(_env_file=None, demo_user_email="  HELLO@example.com  ",
                          demo_user_password="custom-secret", demo_user_display_name=" Custom Admin ")
    user, created = seed_demo_user(db, configured)
    assert created and user.email == "hello@example.com" and user.display_name == "Custom Admin"
    assert verify_password("custom-secret", user.password_hash)
    assert "custom-secret" not in repr(configured)


async def test_login_cookie_hash_and_safe_user(client: httpx.AsyncClient, db: DBSession, demo_user: User) -> None:
    response = await client.post("/api/auth/login", json={**LOGIN, "email": "  ADMIN@ROUTE53.LOCAL  "})
    assert response.status_code == 200
    assert response.json() == {"user": {"id": demo_user.id, "email": LOGIN["email"], "display_name": "Admin User"}}
    cookie = parsed_cookie(response)
    assert cookie["httponly"] and cookie["samesite"] == "lax" and cookie["path"] == "/"
    assert not cookie["secure"] and cookie["max-age"] == "86400" and cookie["expires"]
    assert response.headers["cache-control"] == "no-store"
    saved = db.scalar(select(Session))
    assert saved is not None and saved.user_id == demo_user.id
    assert len(cookie.value) >= 43
    assert saved.token_hash != cookie.value and saved.token_hash == hash_session_token(cookie.value)
    assert len(saved.token_hash) == 64
    assert timedelta(hours=23, minutes=59) < saved.expires_at - utc_now() <= timedelta(hours=24)
    assert cookie.value not in response.text and saved.token_hash not in response.text


@pytest.mark.parametrize("credentials", [
    {**LOGIN, "password": "incorrect"}, {**LOGIN, "email": "unknown@example.com"},
])
async def test_bad_credentials_are_generic(client: httpx.AsyncClient, db: DBSession, credentials: dict[str, str]) -> None:
    response = await client.post("/api/auth/login", json=credentials)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert "set-cookie" not in response.headers
    assert session_count(db) == 0


async def test_inactive_user_cannot_login(client: httpx.AsyncClient, db: DBSession, demo_user: User) -> None:
    demo_user.is_active = False
    db.commit()
    response = await client.post("/api/auth/login", json=LOGIN)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert session_count(db) == 0


@pytest.mark.parametrize("stored_hash", ["unrecognized-hash", "$argon2id$corrupt"])
async def test_corrupt_credentials_fail_closed(client: httpx.AsyncClient, db: DBSession, demo_user: User, stored_hash: str) -> None:
    demo_user.password_hash = stored_hash
    db.commit()
    response = await client.post("/api/auth/login", json=LOGIN)
    assert response.status_code == 401 and response.json() == {"detail": "Invalid email or password"}


@pytest.mark.parametrize("email", ["invalid", "a@@example.com", ".a@example.com", "a..b@example.com", "a@-bad.com", "a@bad_.com"])
async def test_malformed_email_validation(client: httpx.AsyncClient, email: str) -> None:
    response = await client.post("/api/auth/login", json={**LOGIN, "email": email})
    assert response.status_code == 422
    assert LOGIN["password"] not in response.text and "input" not in response.text


@pytest.mark.parametrize("payload", [{"email": LOGIN["email"]}, {**LOGIN, "password": ""}, {**LOGIN, "password": "private" * 200}])
async def test_invalid_password_payload_is_not_echoed(client: httpx.AsyncClient, payload: dict[str, str]) -> None:
    response = await client.post("/api/auth/login", json=payload)
    assert response.status_code == 422 and "input" not in response.text
    assert "private" not in response.text


async def test_authenticated_me_and_last_seen(client: httpx.AsyncClient, db: DBSession) -> None:
    login = await client.post("/api/auth/login", json=LOGIN)
    session = db.scalar(select(Session))
    assert session is not None and session.last_seen_at is None
    me = await client.get("/api/auth/me")
    assert me.status_code == 200 and me.json() == login.json()
    db.refresh(session)
    assert session.last_seen_at is not None and session.last_seen_at <= utc_now()
    assert me.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("token", [None, "not-a-real-session"])
async def test_me_without_valid_session(client: httpx.AsyncClient, token: str | None) -> None:
    headers = {"Cookie": f"route53_session={token}"} if token else {}
    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401 and response.json() == {"detail": "Not authenticated"}
    assert parsed_cookie(response)["max-age"] == "0"


async def test_logout_removes_session_and_cookie_and_is_idempotent(client: httpx.AsyncClient, db: DBSession) -> None:
    await client.post("/api/auth/login", json=LOGIN)
    raw_token = client.cookies.get("route53_session")
    assert session_count(db) == 1
    response = await client.post("/api/auth/logout")
    assert response.status_code == 200 and response.json() == {"message": "Logged out successfully"}
    cookie = parsed_cookie(response)
    assert cookie["max-age"] == "0" and cookie["httponly"] and cookie["path"] == "/"
    assert client.cookies.get("route53_session") is None and session_count(db) == 0
    assert (await client.get("/api/auth/me")).status_code == 401
    # Replaying the deleted cookie cannot authenticate, and logout is still safe.
    headers = {"Cookie": f"route53_session={raw_token}"}
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401
    assert (await client.post("/api/auth/logout", headers=headers)).status_code == 200
    assert (await client.post("/api/auth/logout")).status_code == 200


async def test_expired_session_is_rejected_and_deleted(client: httpx.AsyncClient, db: DBSession, demo_user: User) -> None:
    token = generate_session_token()
    db.add(Session(user_id=demo_user.id, token_hash=hash_session_token(token), expires_at=utc_now() - timedelta(seconds=1)))
    db.commit()
    response = await client.get("/api/auth/me", headers={"Cookie": f"route53_session={token}"})
    assert response.status_code == 401 and session_count(db) == 0
    assert parsed_cookie(response)["max-age"] == "0"


async def test_user_deactivated_after_login(client: httpx.AsyncClient, db: DBSession, demo_user: User) -> None:
    await client.post("/api/auth/login", json=LOGIN)
    demo_user.is_active = False
    db.commit()
    assert (await client.get("/api/auth/me")).status_code == 401
    assert session_count(db) == 0


async def test_deleted_user_cannot_use_session(client: httpx.AsyncClient, db: DBSession, demo_user: User) -> None:
    await client.post("/api/auth/login", json=LOGIN)
    db.delete(demo_user)
    db.commit()
    assert (await client.get("/api/auth/me")).status_code == 401
    assert session_count(db) == 0


async def test_login_cleans_expired_sessions(client: httpx.AsyncClient, db: DBSession, demo_user: User) -> None:
    db.add(Session(user_id=demo_user.id, token_hash=hash_session_token(generate_session_token()), expires_at=utc_now() - timedelta(days=1)))
    db.commit()
    assert (await client.post("/api/auth/login", json=LOGIN)).status_code == 200
    assert session_count(db) == 1
    assert db.scalar(select(Session)).expires_at > utc_now()


async def test_login_rotates_cookie_and_revokes_previous(client: httpx.AsyncClient, db: DBSession) -> None:
    await client.post("/api/auth/login", json=LOGIN)
    old_token = client.cookies.get("route53_session")
    await client.post("/api/auth/login", json=LOGIN)
    assert client.cookies.get("route53_session") != old_token and session_count(db) == 1
    assert (await client.get("/api/auth/me", headers={"Cookie": f"route53_session={old_token}"})).status_code == 401


async def test_logout_preserves_another_clients_session(client: httpx.AsyncClient, application: FastAPI, db: DBSession) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(application), base_url="http://test") as other:
        await client.post("/api/auth/login", json=LOGIN)
        await other.post("/api/auth/login", json=LOGIN)
        assert session_count(db) == 2
        await client.post("/api/auth/logout")
        assert session_count(db) == 1 and (await other.get("/api/auth/me")).status_code == 200


async def test_session_survives_new_application_and_engine(client: httpx.AsyncClient, db_engine: Engine, settings: Settings) -> None:
    login = await client.post("/api/auth/login", json=LOGIN)
    token = client.cookies.get("route53_session")
    # No shared ORM session or engine: reconnect to the persisted migrated file.
    restarted_engine = create_engine(db_engine.url)
    event.listen(restarted_engine, "connect", enable_sqlite_foreign_keys)
    try:
        restarted_app = isolated_app(restarted_engine, settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(restarted_app), base_url="http://test") as fresh:
            response = await fresh.get("/api/auth/me", headers={"Cookie": f"route53_session={token}"})
            assert response.status_code == 200 and response.json() == login.json()
    finally:
        restarted_engine.dispose()


async def test_configurable_cookie_and_ttl(application: FastAPI, settings: Settings, db: DBSession) -> None:
    settings.session_cookie_name = "custom_session"
    settings.session_cookie_secure = True
    settings.session_ttl_hours = 2
    async with httpx.AsyncClient(transport=httpx.ASGITransport(application), base_url="https://test") as secure_client:
        login = await secure_client.post("/api/auth/login", json=LOGIN)
        cookie = parsed_cookie(login, "custom_session")
        assert cookie["secure"] and cookie["max-age"] == "7200" and cookie["httponly"]
        assert (await secure_client.get("/api/auth/me")).status_code == 200
        saved = db.scalar(select(Session))
        assert saved is not None and timedelta(hours=1, minutes=59) < saved.expires_at - utc_now() <= timedelta(hours=2)
        logout = await secure_client.post("/api/auth/logout")
        cleared = parsed_cookie(logout, "custom_session")
        assert cleared["max-age"] == "0" and cleared["secure"] and cleared["httponly"]


def test_cookie_configuration_defaults_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    assert Settings(_env_file=None, app_env="production").session_cookie_secure is True
    assert Settings(_env_file=None, app_env="development").session_cookie_secure is False
    assert Settings(_env_file=None, app_env="production", session_cookie_secure=False).session_cookie_secure is False
    for fields in [{"session_ttl_hours": 0}, {"session_ttl_hours": -1}, {"session_cookie_name": "bad;name"},
                   {"demo_user_email": "invalid"}, {"demo_user_display_name": "   "}, {"demo_user_password": ""}]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **fields)


async def test_reusable_current_user_dependency(client: httpx.AsyncClient, application: FastAPI) -> None:
    @application.get("/test-protected")
    def protected(user: CurrentUser) -> dict[str, int]:
        return {"user_id": user.id}

    assert (await client.get("/test-protected")).status_code == 401
    await client.post("/api/auth/login", json=LOGIN)
    assert (await client.get("/test-protected")).status_code == 200


async def test_auth_cors_and_untrusted_browser_origin(client: httpx.AsyncClient, db: DBSession) -> None:
    response = await client.post("/api/auth/login", json=LOGIN, headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
    rejected = await client.post("/api/auth/logout", headers={"Origin": "http://localhost:9999"})
    assert rejected.status_code == 403 and session_count(db) == 1
    assert "access-control-allow-origin" not in rejected.headers
    rejected_login = await client.post("/api/auth/login", json=LOGIN, headers={"Origin": "http://untrusted.example"})
    assert rejected_login.status_code == 403 and session_count(db) == 1
    assert (await client.post("/api/auth/logout", headers={"Origin": "http://test"})).status_code == 200


async def test_openapi_auth_schemas_are_public(client: httpx.AsyncClient) -> None:
    schema = (await client.get("/openapi.json")).json()
    for path, method in [("/api/auth/login", "post"), ("/api/auth/me", "get"), ("/api/auth/logout", "post")]:
        assert schema["paths"][path][method]["tags"] == ["Authentication"]
    assert set(schema["components"]["schemas"]["AuthUserResponse"]["properties"]) == {"id", "email", "display_name"}
    password = schema["components"]["schemas"]["LoginRequest"]["properties"]["password"]
    assert password["writeOnly"] and password["format"] == "password"
    assert not any(field in str(schema) for field in ["password_hash", "token_hash", "raw_token"])
