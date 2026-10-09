from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.database import enable_sqlite_foreign_keys
from app.dependencies import database
from app.main import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    monkeypatch.setenv("APP_NAME", "Route53 Clone API")
    get_settings.cache_clear()
    transport = httpx.ASGITransport(app=create_app())
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client
    finally:
        get_settings.cache_clear()


async def test_root_and_health(client: httpx.AsyncClient) -> None:
    root = await client.get("/")
    assert root.status_code == 200
    assert root.json() == {"message": "Route53 Clone API"}
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "route53-clone-api"}


async def test_docs_and_openapi(client: httpx.AsyncClient) -> None:
    assert (await client.get("/docs")).status_code == 200
    assert (await client.get("/redoc")).status_code == 200
    schema = (await client.get("/openapi.json")).json()
    assert schema["info"]["title"] == "Route53 Clone API"
    assert set(schema["paths"]) == {
        "/", "/health", "/api/auth/register", "/api/auth/login", "/api/auth/me", "/api/auth/logout",
        "/api/hosted-zones", "/api/hosted-zones/{zone_id}",
        "/api/hosted-zones/{zone_id}/records", "/api/hosted-zones/{zone_id}/records/{record_id}",
    }


async def test_credentialed_cors(client: httpx.AsyncClient) -> None:
    response = await client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"
    rejected = await client.options(
        "/health",
        headers={
            "Origin": "http://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers


async def test_configured_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:4000")
    get_settings.cache_clear()
    try:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health", headers={"Origin": "http://localhost:4000"})
            assert response.headers["access-control-allow-origin"] == "http://localhost:4000"
    finally:
        get_settings.cache_clear()


def test_origin_rejects_wildcard_and_paths() -> None:
    for value in ["*", "http://localhost:3000/app", "http://user:pass@localhost:3000"]:
        with pytest.raises(ValidationError):
            Settings(frontend_origin=value, _env_file=None)


@pytest.mark.parametrize("request_fails", [False, True])
def test_sqlite_and_session_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request_fails: bool
) -> None:
    test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    event.listen(test_engine, "connect", enable_sqlite_foreign_keys)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=test_engine))
    dependency = database.get_db()
    session = next(dependency)
    try:
        assert session.scalar(text("SELECT 1")) == 1
        assert session.scalar(text("PRAGMA foreign_keys")) == 1
        assert session.scalar(text("SELECT count(*) FROM sqlite_master WHERE type='table'")) == 0
    finally:
        if request_fails:
            with pytest.raises(RuntimeError, match="request failed"):
                dependency.throw(RuntimeError("request failed"))
        else:
            dependency.close()
    assert test_engine.pool.checkedout() == 0
    test_engine.dispose()
