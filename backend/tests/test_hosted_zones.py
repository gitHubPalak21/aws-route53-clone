from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta, timezone
import re

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings, get_settings
from app.core.security import hash_password, hash_session_token
from app.db.database import enable_sqlite_foreign_keys
from app.db.types import utc_now
from app.dependencies.database import get_db
from app.main import create_app
from app.models import DNSRecord, HostedZone, Session, User
from app.models.enums import DNSRecordType, ZoneType
from app.schemas.hosted_zone import HostedZoneCreate, HostedZoneUpdate
from app.services import hosted_zone_service as service

pytestmark = pytest.mark.anyio
BASE = "/api/hosted-zones"
PRIVATE = {"zone_type": "PRIVATE", "vpc_id": "vpc-0123456789abcdef", "region": "ap-south-1"}
PUBLIC_FIELDS = {"id", "name", "comment", "zone_type", "vpc_id", "region", "record_count", "created_at", "updated_at"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
def password_hash() -> str:
    return hash_password("test-secret")


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:3000")
    get_settings.cache_clear()
    yield Settings(_env_file=None, frontend_origin="http://localhost:3000",
                   session_cookie_name="route53_session", session_cookie_secure=False)
    get_settings.cache_clear()


@pytest.fixture
def users(db: DBSession, password_hash: str) -> tuple[User, User]:
    first = User(email="first@example.com", display_name="First", password_hash=password_hash)
    second = User(email="second@example.com", display_name="Second", password_hash=password_hash)
    db.add_all([first, second])
    db.commit()
    return first, second


def isolated_app(engine: Engine, settings: Settings) -> FastAPI:
    application = create_app()

    def test_db() -> Iterator[DBSession]:
        with DBSession(engine, autoflush=False, expire_on_commit=False) as session:
            yield session

    application.dependency_overrides[get_db] = test_db
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest.fixture
def application(db_engine: Engine, settings: Settings, users: tuple[User, User]) -> FastAPI:
    return isolated_app(db_engine, settings)


async def sign_in(client: httpx.AsyncClient, email: str = "first@example.com") -> None:
    response = await client.post("/api/auth/login", json={"email": email, "password": "test-secret"})
    assert response.status_code == 200
    assert "route53_session" in client.cookies


@pytest.fixture
async def client(application: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(application), base_url="http://test") as client:
        await sign_in(client)
        yield client


async def create(client: httpx.AsyncClient, name: str = "example.com", **fields) -> dict:
    response = await client.post(BASE, json={"name": name, **fields})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


@pytest.mark.parametrize("method,path,payload", [
    ("GET", BASE, None), ("POST", BASE, {"name": "example.com"}),
    ("GET", BASE + "/ZABSENT", None), ("PATCH", BASE + "/ZABSENT", {"comment": "updated"}),
    ("DELETE", BASE + "/ZABSENT", None),
])
async def test_all_routes_require_auth(application: FastAPI, method: str, path: str, payload: dict | None) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(application), base_url="http://test") as client:
        response = await client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.parametrize("state", ["expired", "revoked", "inactive"])
async def test_invalid_session_cannot_list(client: httpx.AsyncClient, db: DBSession, users: tuple[User, User], state: str) -> None:
    session = db.scalar(select(Session).where(Session.token_hash == hash_session_token(client.cookies["route53_session"])))
    assert session is not None
    if state == "expired":
        session.expires_at = utc_now() - timedelta(seconds=1)
    elif state == "revoked":
        db.delete(session)
    else:
        users[0].is_active = False
    db.commit()
    assert (await client.get(BASE)).status_code == 401


async def test_create_public_id_defaults_timestamps_and_storage(client: httpx.AsyncClient, db: DBSession, users: tuple[User, User]) -> None:
    zone = await create(client, " Example.COM. ", comment="Production website")
    assert set(zone) == PUBLIC_FIELDS
    assert re.fullmatch(r"Z[A-Z0-9]{20}", zone["id"])
    assert zone["name"] == "example.com" and zone["zone_type"] == "PUBLIC"
    assert zone["vpc_id"] is None and zone["region"] is None and zone["record_count"] == 2
    for key in ("created_at", "updated_at"):
        assert datetime.fromisoformat(zone[key]).utcoffset() == timedelta(0)
    saved = db.get(HostedZone, zone["id"])
    assert saved is not None and saved.owner_id == users[0].id and saved.name == "example.com"
    assert db.scalar(select(func.count()).select_from(DNSRecord)) == 2
    assert "record_count" not in HostedZone.__table__.columns


async def test_create_private_and_trim_metadata(client: httpx.AsyncClient) -> None:
    zone = await create(client, "internal.company.local", **{**PRIVATE,
        "vpc_id": " vpc-0123456789abcdef ", "region": " ap-south-1 "})
    assert zone["vpc_id"] == PRIVATE["vpc_id"] and zone["region"] == PRIVATE["region"]
    assert zone["zone_type"] == "PRIVATE" and zone["record_count"] == 2


@pytest.mark.parametrize("fields", [{}, PRIVATE])
async def test_system_records_visible_in_create_detail_list_and_persisted(client: httpx.AsyncClient, db: DBSession, fields: dict) -> None:
    zone = await create(client, **fields)
    assert zone["record_count"] == 2
    assert (await client.get(BASE + "/" + zone["id"])).json()["record_count"] == 2
    assert (await client.get(BASE)).json()["items"][0]["record_count"] == 2
    stored = list(db.scalars(select(DNSRecord).where(DNSRecord.hosted_zone_id == zone["id"])))
    assert len(stored) == 2 and all(record.is_system for record in stored)
    assert {record.record_type for record in stored} == {DNSRecordType.NS, DNSRecordType.SOA}


@pytest.mark.parametrize("name", ["localhost", "a", "a-b.example.com", "123.example", "api.example.co.uk",
                                    "a" * 63 + ".com", ".".join(["a" * 63] * 3 + ["b" * 61]) + "."])
async def test_valid_domain_boundaries(client: httpx.AsyncClient, name: str) -> None:
    zone = await create(client, name)
    assert zone["name"] == name.removesuffix(".")


@pytest.mark.parametrize("name", ["", "  ", ".", "example..com", ".example.com", "example.com..",
    "bad name.com", "bad\tname.com", "-bad.com", "bad-.com", "bad_name.com", "éxample.com",
    "https://example.com", "*.example.com", "a" * 64 + ".com", ".".join(["a" * 63] * 4), None, 123])
async def test_invalid_domain(client: httpx.AsyncClient, db: DBSession, name: object) -> None:
    response = await client.post(BASE, json={"name": name})
    assert response.status_code == 422
    assert db.scalar(select(func.count()).select_from(HostedZone)) == 0


@pytest.mark.parametrize("fields", [
    {"zone_type": "PRIVATE"}, {"zone_type": "PRIVATE", "vpc_id": PRIVATE["vpc_id"]},
    {"zone_type": "PRIVATE", "region": "us-east-1"}, {**PRIVATE, "vpc_id": ""},
    {**PRIVATE, "vpc_id": "wrong-12345678"}, {**PRIVATE, "vpc_id": "vpc-xyzxyzxy"},
    {**PRIVATE, "vpc_id": "vpc-123"}, {**PRIVATE, "vpc_id": "vpc-" + "a" * 18},
    {**PRIVATE, "region": "moon-east-1"}, {**PRIVATE, "region": ""}, {**PRIVATE, "region": None},
    {"vpc_id": PRIVATE["vpc_id"]}, {"region": "us-east-1"},
    {"zone_type": "INVALID"}, {"zone_type": None}, {"comment": "x" * 1025},
])
async def test_invalid_create_metadata(client: httpx.AsyncClient, fields: dict) -> None:
    response = await client.post(BASE, json={"name": "example.com", **fields})
    assert response.status_code == 422


@pytest.mark.parametrize("extra", ["id", "owner_id", "record_count", "created_at", "updated_at", "unknown"])
async def test_mass_assignment_rejected(client: httpx.AsyncClient, db: DBSession, extra: str) -> None:
    response = await client.post(BASE, json={"name": "example.com", extra: "injected"})
    assert response.status_code == 422
    zone = await create(client)
    response = await client.patch(BASE + "/" + zone["id"], json={extra: "injected"})
    assert response.status_code == 422
    assert (await client.get(BASE + "/" + zone["id"])).json() == zone
    assert db.scalar(select(func.count()).select_from(HostedZone)) == 1


async def test_duplicate_domains_allowed_same_and_other_owner(client: httpx.AsyncClient) -> None:
    first = await create(client)
    second = await create(client, "EXAMPLE.COM.")
    await sign_in(client, "second@example.com")
    third = await create(client)
    assert len({first["id"], second["id"], third["id"]}) == 3
    assert first["name"] == second["name"] == third["name"]


async def test_empty_list(client: httpx.AsyncClient) -> None:
    response = await client.get(BASE)
    assert response.status_code == 200
    assert response.json() == {"items": [], "page": 1, "page_size": 20, "total": 0, "pages": 0}
    assert response.headers["cache-control"] == "no-store"


async def test_owner_isolation_for_all_operations(client: httpx.AsyncClient) -> None:
    secret = await create(client, "secret.example.com", comment="private owner comment")
    await sign_in(client, "second@example.com")
    own = await create(client, "own.example.com")
    for params in ({}, {"search": "secret"}, {"search": secret["id"]}, {"search": "private owner comment"}):
        response = (await client.get(BASE, params=params)).json()
        assert response["total"] == (1 if not params else 0)
        assert all(item["id"] == own["id"] for item in response["items"])
    for method, body in [("GET", None), ("PATCH", {"name": "stolen.com"}), ("DELETE", None)]:
        hidden = await client.request(method, BASE + "/" + secret["id"], json=body)
        missing = await client.request(method, BASE + "/ZABSENT", json=body)
        assert hidden.status_code == missing.status_code == 404
        assert hidden.json() == missing.json() == {"detail": "Hosted zone not found"}
    await sign_in(client)
    assert (await client.get(BASE + "/" + secret["id"])).json() == secret


async def test_search_name_comment_id_literal_wildcards_and_injection(client: httpx.AsyncClient) -> None:
    first = await create(client, "Prod.example.com", comment="Critical 100%_ service /path")
    await create(client, "staging.example.com", comment="Other")
    for term in (" PROD ", "cRiTiCaL", first["id"].lower(), "100%_", "%", "_", "/path"):
        result = (await client.get(BASE, params={"search": term})).json()
        assert result["total"] == 1 and result["items"][0]["id"] == first["id"]
    for term in ("missing", "' OR 1=1 --"):
        result = (await client.get(BASE, params={"search": term})).json()
        assert result["total"] == result["pages"] == 0 and result["items"] == []
    assert (await client.get(BASE, params={"search": " "})).json()["total"] == 2


async def test_pagination_search_type_and_sort_combine(client: httpx.AsyncClient) -> None:
    for name in ("a.prod.com", "b.prod.com", "c.prod.com"):
        await create(client, name, **PRIVATE)
    await create(client, "d.prod.com")
    await create(client, "unrelated.com", **PRIVATE)
    query = {"search": "PROD", "zone_type": "PRIVATE", "page_size": 2, "sort_by": "name", "sort_order": "desc"}
    first = (await client.get(BASE, params=query)).json()
    second = (await client.get(BASE, params={**query, "page": 2})).json()
    third = (await client.get(BASE, params={**query, "page": 3})).json()
    assert first["page"] == 1 and first["page_size"] == 2 and first["total"] == 3 and first["pages"] == 2
    assert [z["name"] for z in first["items"]] == ["c.prod.com", "b.prod.com"]
    assert [z["name"] for z in second["items"]] == ["a.prod.com"]
    assert third["items"] == [] and third["total"] == 3 and third["pages"] == 2
    public = (await client.get(BASE, params={"zone_type": "PUBLIC"})).json()
    assert public["total"] == 1 and public["items"][0]["name"] == "d.prod.com"


@pytest.mark.parametrize("params", [
    {"page": 0}, {"page": -1}, {"page": "abc"}, {"page": 2_147_483_648},
    {"page_size": 0}, {"page_size": 101}, {"page_size": -1}, {"page_size": 1.5},
    {"sort_by": "password_hash"}, {"sort_by": "name; DROP TABLE users"}, {"sort_order": "random"},
    {"zone_type": "private"}, {"search": "x" * 254}, {"unknown": "value"},
])
async def test_query_validation(client: httpx.AsyncClient, params: dict) -> None:
    assert (await client.get(BASE, params=params)).status_code == 422


@pytest.mark.parametrize("sort_by", ["name", "zone_type", "created_at", "updated_at", "id"])
@pytest.mark.parametrize("order", ["asc", "desc"])
async def test_whitelisted_sorting(client: httpx.AsyncClient, db: DBSession, users: tuple[User, User], sort_by: str, order: str) -> None:
    when = datetime(2025, 1, 1, tzinfo=timezone.utc)
    entries = [
        HostedZone(id="ZC", owner_id=users[0].id, name="a.com", zone_type=ZoneType.PUBLIC,
                   created_at=when, updated_at=when + timedelta(days=2)),
        HostedZone(id="ZA", owner_id=users[0].id, name="b.com", zone_type=ZoneType.PRIVATE,
                   vpc_id=PRIVATE["vpc_id"], region=PRIVATE["region"], created_at=when + timedelta(days=1), updated_at=when),
        HostedZone(id="ZB", owner_id=users[0].id, name="c.com", zone_type=ZoneType.PUBLIC,
                   created_at=when + timedelta(days=2), updated_at=when + timedelta(days=1)),
    ]
    db.add_all(entries)
    db.commit()
    expected = sorted(entries, key=lambda z: z.id)
    expected.sort(key=lambda z: getattr(z, sort_by), reverse=order == "desc")
    result = (await client.get(BASE, params={"sort_by": sort_by, "sort_order": order})).json()
    assert [z["id"] for z in result["items"]] == [z.id for z in expected]


async def test_sort_ties_are_stable_across_pages(client: httpx.AsyncClient, db: DBSession, users: tuple[User, User]) -> None:
    when = utc_now()
    db.add_all([HostedZone(id=zone_id, owner_id=users[0].id, name="same.com", created_at=when, updated_at=when)
                for zone_id in ("ZC", "ZA", "ZB")])
    db.commit()
    for sort_by in ("name", "zone_type", "created_at", "updated_at"):
        ids = []
        for page in range(1, 4):
            result = (await client.get(BASE, params={"sort_by": sort_by, "sort_order": "desc", "page_size": 1, "page": page})).json()
            ids.append(result["items"][0]["id"])
        assert ids == ["ZA", "ZB", "ZC"]


@pytest.mark.parametrize("zone_id", ["wrong", "Z", "z123", "Zbad", "Z" + "A" * 32, "ZABC%27"])
async def test_path_validation(client: httpx.AsyncClient, zone_id: str) -> None:
    for method, body in [("GET", None), ("PATCH", {"comment": "ok"}), ("DELETE", None)]:
        assert (await client.request(method, BASE + "/" + zone_id, json=body)).status_code == 422


async def test_detail_patch_preserve_identity_and_timestamp(client: httpx.AsyncClient, db: DBSession) -> None:
    zone = await create(client, comment="Old comment")
    assert (await client.get(BASE + "/" + zone["id"])).json() == zone
    changed = await client.patch(BASE + "/" + zone["id"], json={"name": " NEW.Example.COM. "})
    assert changed.status_code == 200
    updated = changed.json()
    assert updated["id"] == zone["id"] and updated["created_at"] == zone["created_at"]
    assert updated["name"] == "new.example.com" and updated["comment"] == "Old comment"
    assert datetime.fromisoformat(updated["updated_at"]) > datetime.fromisoformat(zone["updated_at"])
    cleared = (await client.patch(BASE + "/" + zone["id"], json={"comment": None})).json()
    assert cleared["comment"] is None and cleared["name"] == updated["name"]
    unchanged = (await client.patch(BASE + "/" + zone["id"], json={"name": updated["name"]})).json()
    assert datetime.fromisoformat(unchanged["updated_at"]) > datetime.fromisoformat(cleared["updated_at"])
    assert db.scalar(select(func.count()).select_from(HostedZone)) == 1


@pytest.mark.parametrize("initial_type", ["PUBLIC", "PRIVATE"])
@pytest.mark.parametrize("include_metadata", [False, True])
async def test_zone_type_is_immutable_and_rejection_is_atomic(
    client: httpx.AsyncClient, db: DBSession, initial_type: str, include_metadata: bool,
) -> None:
    zone = await create(client, **(PRIVATE if initial_type == "PRIVATE" else {}))
    path = BASE + "/" + zone["id"]
    before = [(row.id, row.name, list(row.values), row.updated_at)
              for row in db.scalars(select(DNSRecord).where(DNSRecord.hosted_zone_id == zone["id"]).order_by(DNSRecord.id))]
    payload = {"zone_type": "PRIVATE" if initial_type == "PUBLIC" else "PUBLIC", "comment": "Must not save", "name": "changed.example.com"}
    if include_metadata:
        payload.update(vpc_id=PRIVATE["vpc_id"], region=PRIVATE["region"])
    rejected = await client.patch(path, json=payload)
    assert rejected.status_code == 409
    assert "type cannot be changed" in rejected.json()["detail"]
    assert rejected.headers["cache-control"] == "no-store"
    assert (await client.get(path)).json() == zone
    db.expire_all()
    assert [(row.id, row.name, list(row.values), row.updated_at)
            for row in db.scalars(select(DNSRecord).where(DNSRecord.hosted_zone_id == zone["id"]).order_by(DNSRecord.id))] == before
    # Existing clients may still include an unchanged type with an ordinary edit.
    updated = await client.patch(path, json={"zone_type": initial_type, "comment": "Saved"})
    assert updated.status_code == 200 and updated.json()["zone_type"] == initial_type
    assert updated.json()["comment"] == "Saved" and updated.json()["record_count"] == 2


async def test_private_partial_metadata_remains_editable(client: httpx.AsyncClient) -> None:
    zone = await create(client, **PRIVATE)
    path = BASE + "/" + zone["id"]
    partial = await client.patch(path, json={"region": "us-east-1", "comment": "Internal"})
    assert partial.status_code == 200 and partial.json()["vpc_id"] == PRIVATE["vpc_id"]
    invalid = await client.patch(path, json={"vpc_id": None})
    assert invalid.status_code == 422
    assert (await client.get(path)).json() == partial.json()


@pytest.mark.parametrize("payload", [{}, {"name": None}, {"zone_type": None}, {"name": "bad..com"},
    {"zone_type": "INVALID"}, {"vpc_id": "invalid"}, {"region": "unsupported"},
    {"comment": "x" * 1025}, {"vpc_id": PRIVATE["vpc_id"]}, {"region": "us-east-1"}])
async def test_invalid_patch_is_atomic(client: httpx.AsyncClient, payload: dict) -> None:
    zone = await create(client)
    path = BASE + "/" + zone["id"]
    assert (await client.patch(path, json=payload)).status_code == 422
    assert (await client.get(path)).json() == zone


async def test_patch_duplicate_name_allowed(client: httpx.AsyncClient) -> None:
    first = await create(client, "first.com")
    second = await create(client, "second.com")
    response = await client.patch(BASE + "/" + second["id"], json={"name": first["name"]})
    assert response.status_code == 200 and response.json()["name"] == first["name"]


async def test_counts_query_efficiency_and_delete_cascade(client: httpx.AsyncClient, db: DBSession, db_engine: Engine) -> None:
    first = await create(client)
    second = await create(client, "empty.com")
    db.add_all([DNSRecord(hosted_zone_id=first["id"], name=f"host{index}.{first['name']}", record_type=DNSRecordType.A,
                          values=["192.0.2.1"]) for index in range(3)])
    db.commit()
    assert (await client.get(BASE + "/" + first["id"])).json()["record_count"] == 5
    result = (await client.get(BASE)).json()
    assert {z["id"]: z["record_count"] for z in result["items"]} == {first["id"]: 5, second["id"]: 2}
    assert (await client.patch(BASE + "/" + first["id"], json={"comment": "Count retained"})).json()["record_count"] == 5
    statements: list[str] = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_engine, "before_cursor_execute", capture)
    try:
        await client.get(BASE, params={"page_size": 1})
        one_count = len(statements)
        statements.clear()
        await client.get(BASE, params={"page_size": 100})
        assert len(statements) == one_count
        zone_queries = [sql for sql in statements if "FROM hosted_zones" in sql]
        assert len(zone_queries) == 2
        assert "LIMIT" in zone_queries[1] and "OFFSET" in zone_queries[1]
        assert "count(dns_records.id)" in zone_queries[1]
        assert not any(sql.lstrip().startswith("SELECT dns_records.") for sql in statements)
    finally:
        event.remove(db_engine, "before_cursor_execute", capture)
    response = await client.delete(BASE + "/" + first["id"])
    assert response.status_code == 204 and response.content == b""
    assert db.scalar(select(func.count()).select_from(DNSRecord)) == 2
    assert db.scalar(select(func.count()).select_from(DNSRecord).where(DNSRecord.hosted_zone_id == first["id"])) == 0
    assert (await client.get(BASE + "/" + first["id"])).status_code == 404
    assert (await client.delete(BASE + "/" + first["id"])).status_code == 404
    assert (await client.get(BASE + "/" + second["id"])).status_code == 200


async def test_persistence_new_engine_and_app(client: httpx.AsyncClient, db_engine: Engine, settings: Settings) -> None:
    zone = await create(client, "persistent.local")
    cookie = client.cookies["route53_session"]
    fresh_engine = create_engine(db_engine.url)
    event.listen(fresh_engine, "connect", enable_sqlite_foreign_keys)
    try:
        application = isolated_app(fresh_engine, settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(application), base_url="http://test",
                                     headers={"Cookie": "route53_session=" + cookie}) as fresh_client:
            assert (await fresh_client.get(BASE + "/" + zone["id"])).json() == zone
            assert (await fresh_client.get(BASE)).json()["total"] == 1
    finally:
        fresh_engine.dispose()


async def test_known_id_collision_retry_and_exhaustion(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    existing = await create(client)
    candidates = iter([existing["id"], "ZNEWID"])
    monkeypatch.setattr(service, "generate_hosted_zone_id", lambda: next(candidates))
    new = await create(client, "retry.com")
    assert new["id"] == "ZNEWID"
    monkeypatch.setattr(service, "generate_hosted_zone_id", lambda: existing["id"])
    response = await client.post(BASE, json={"name": "failed.com"})
    assert response.status_code == 503 and response.headers["retry-after"] == "1"
    assert (await client.get(BASE)).json()["total"] == 2


def test_race_collision_retries_after_rollback(db: DBSession, db_engine: Engine, users: tuple[User, User], monkeypatch: pytest.MonkeyPatch) -> None:
    first_id, second_id = users[0].id, users[1].id
    candidates = iter(["ZRACE", "ZRETRY"])
    monkeypatch.setattr(service, "generate_hosted_zone_id", lambda: next(candidates))
    real_commit = service.commit_change
    calls = 0

    def race_commit(session: DBSession) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            with DBSession(db_engine) as other:
                other.add(HostedZone(id="ZRACE", owner_id=second_id, name="other.com"))
                other.commit()
        real_commit(session)

    monkeypatch.setattr(service, "commit_change", race_commit)
    result = service.create_hosted_zone(db, first_id, HostedZoneCreate(name="retry.com"))
    assert result.id == "ZRETRY" and calls == 2 and db.is_active
    assert db.get(HostedZone, "ZRACE").owner_id == second_id
    assert db.scalar(select(func.count()).select_from(HostedZone)) == 2
    assert db.scalar(select(func.count()).select_from(DNSRecord)) == 2
    assert db.scalar(select(func.count()).select_from(DNSRecord).where(DNSRecord.hosted_zone_id == "ZRACE")) == 0


def test_unrelated_integrity_failure_rolls_back_and_propagates(db: DBSession, users: tuple[User, User]) -> None:
    with pytest.raises(IntegrityError):
        service.create_hosted_zone(db, -100, HostedZoneCreate(name="bad-owner.com"))
    assert db.is_active and db.scalar(select(func.count()).select_from(HostedZone)) == 0
    result = service.create_hosted_zone(db, users[0].id, HostedZoneCreate(name="valid.com"))
    assert result.name == "valid.com"


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_database_error_rollback(db: DBSession, users: tuple[User, User], monkeypatch: pytest.MonkeyPatch, operation: str) -> None:
    owner_id = users[0].id
    zone = service.create_hosted_zone(db, owner_id, HostedZoneCreate(name="original.com"))

    def broken_commit() -> None:
        db.flush()  # Exercise rollback of actual INSERT/UPDATE/DELETE statements.
        raise SQLAlchemyError("Simulated database failure")

    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", broken_commit)
        with pytest.raises(SQLAlchemyError, match="Simulated"):
            if operation == "create":
                service.create_hosted_zone(db, owner_id, HostedZoneCreate(name="new.com"))
            elif operation == "update":
                service.update_hosted_zone(db, owner_id, zone.id, HostedZoneUpdate(name="changed.com"))
            else:
                service.delete_hosted_zone(db, owner_id, zone.id)
    assert db.is_active and db.scalar(select(func.count()).select_from(HostedZone)) == 1
    assert service.get_hosted_zone(db, owner_id, zone.id) == zone


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
async def test_untrusted_origin_rejected(client: httpx.AsyncClient, method: str) -> None:
    zone = await create(client)
    path = BASE if method == "POST" else BASE + "/" + zone["id"]
    response = await client.request(method, path, json={"name": "changed.com"}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert (await client.get(BASE + "/" + zone["id"])).json() == zone


async def test_swagger_documents_public_models_and_queries(client: httpx.AsyncClient, db_engine: Engine) -> None:
    schema = (await client.get("/openapi.json")).json()
    paths = schema["paths"]
    for path, methods in [(BASE, ["get", "post"]), (BASE + "/{zone_id}", ["get", "patch", "delete"])]:
        for method in methods:
            operation = paths[path][method]
            assert operation["tags"] == ["Hosted Zones"] and "401" in operation["responses"]
            assert operation["security"] == [{"SessionCookie": []}]
    list_op = paths[BASE]["get"]
    assert {p["name"] for p in list_op["parameters"]} == {"page", "page_size", "search", "sort_by", "sort_order", "zone_type"}
    assert paths[BASE]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("HostedZoneCreate")
    assert paths[BASE + "/{zone_id}"]["patch"]["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("HostedZoneUpdate")
    response_fields = schema["components"]["schemas"]["HostedZoneResponse"]["properties"]
    assert set(response_fields) == PUBLIC_FIELDS
    assert "content" not in paths[BASE + "/{zone_id}"]["delete"]["responses"]["204"]
    assert schema["components"]["securitySchemes"]["SessionCookie"]["in"] == "cookie"
    assert schema["components"]["securitySchemes"]["SessionCookie"]["name"] == "route53_session"
    assert "record_count" not in {c["name"] for c in inspect(db_engine).get_columns("hosted_zones")}
