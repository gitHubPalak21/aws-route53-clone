"""Record API integration against migrated, isolated SQLite and real auth."""

from datetime import datetime
from uuid import UUID

import httpx
import pytest
from sqlalchemy import event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.models import DNSRecord
from app.models.enums import DNSRecordType
from app.schemas.dns_record import DNSRecordCreate, DNSRecordListQuery, DNSRecordUpdate
from app.services import dns_record_service as service

# Reuse the established cookie-authenticated API fixtures rather than a second auth harness.
from test_hosted_zones import (  # noqa: F401
    anyio_backend, application, client, password_hash, settings, sign_in, users,
)

pytestmark = pytest.mark.anyio
BASE = "/api/hosted-zones"
FIELDS = {"id", "hosted_zone_id", "name", "record_type", "values", "ttl", "routing_policy",
          "alias", "alias_target", "is_system", "created_at", "updated_at"}


@pytest.fixture
async def zone(client: httpx.AsyncClient) -> dict:
    response = await client.post(BASE, json={"name": "example.com"})
    assert response.status_code == 201
    return response.json()


def path(zone: dict, record_id: str | None = None) -> str:
    result = f"{BASE}/{zone['id']}/records"
    return result + f"/{record_id}" if record_id else result


async def create(client: httpx.AsyncClient, zone: dict, **fields) -> dict:
    payload = {"name": "www", "record_type": "A", "values": ["192.0.2.10"], **fields}
    response = await client.post(path(zone), json=payload)
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


@pytest.mark.parametrize("method,suffix,payload", [
    ("GET", "", None), ("POST", "", {"name": "www", "record_type": "A", "values": ["192.0.2.1"]}),
    ("GET", "/missing", None), ("PATCH", "/missing", {"ttl": 600}), ("DELETE", "/missing", None),
])
async def test_all_record_routes_require_auth(application, method, suffix, payload):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(application), base_url="http://test") as anonymous:
        response = await anonymous.request(method, BASE + "/ZUNKNOWN/records" + suffix, json=payload)
    assert response.status_code == 401


@pytest.mark.parametrize("method,single,payload", [
    ("GET", False, None), ("POST", False, {"name": "www", "record_type": "A", "values": ["192.0.2.1"]}),
    ("GET", True, None), ("PATCH", True, {"values": ["192.0.2.50"]}), ("DELETE", True, None),
])
async def test_other_owner_and_missing_zone_return_same_404(client, zone, db, method, single, payload):
    record = await create(client, zone)
    await sign_in(client, "second@example.com")
    url = path(zone, record["id"] if single else None)
    denied = await client.request(method, url, json=payload)
    missing = await client.request(method, url.replace(zone["id"], "ZUNKNOWN"), json=payload)
    assert denied.status_code == missing.status_code == 404
    assert denied.json() == missing.json()
    db.expire_all()
    assert db.get(DNSRecord, record["id"]).values == ["192.0.2.10"]


@pytest.mark.parametrize("method,payload", [("GET", None), ("PATCH", {"ttl": 500}), ("DELETE", None)])
async def test_record_id_is_scoped_to_exact_zone(client, zone, method, payload):
    record = await create(client, zone)
    second = (await client.post(BASE, json={"name": "example.com"})).json()
    response = await client.request(method, path(second, record["id"]), json=payload)
    assert response.status_code == 404
    assert (await client.get(path(zone, record["id"]))).status_code == 200


async def test_new_zone_lists_system_records_and_serializes_public_fields(client, zone):
    listed = (await client.get(path(zone))).json()
    assert (listed["page"], listed["page_size"], listed["total"], listed["pages"]) == (1, 20, 2, 1)
    assert {r["record_type"] for r in listed["items"]} == {"NS", "SOA"}
    for record in listed["items"]:
        assert set(record) == FIELDS
        assert UUID(record["id"]).version == 4
        assert record["is_system"] is True and record["alias"] is False
        assert record["hosted_zone_id"] == zone["id"]
        assert (await client.get(path(zone, record["id"]))).json() == record


@pytest.mark.parametrize("record_type,values,expected", [
    ("A", ["192.0.2.1", "192.0.2.2"], ["192.0.2.1", "192.0.2.2"]),
    ("AAAA", ["2001:0DB8:0:0::1", "2001:db8::2"], ["2001:db8::1", "2001:db8::2"]),
    ("CNAME", [" Target.EXAMPLE.NET. "], ["target.example.net."]),
    ("TXT", ['"v=spf1 include:_spf.example.com ~all"', "verification=ABC"], ["v=spf1 include:_spf.example.com ~all", "verification=ABC"]),
    ("MX", ["010 MAIL.EXAMPLE.COM.", "20 backup.example.net"], ["10 mail.example.com.", "20 backup.example.net."]),
    ("NS", ["NS1.Provider.COM", "ns2.provider.com."], ["ns1.provider.com.", "ns2.provider.com."]),
    ("PTR", ["Host.Example.COM"], ["host.example.com."]),
    ("SRV", ["10 5 443 SERVICE.EXAMPLE.NET."], ["10 5 443 service.example.net."]),
    ("CAA", ['0 ISSUE "letsencrypt.org"', "128 iodef mailto:security@example.com", "0 custom value with spaces"],
     ["0 issue letsencrypt.org", "128 iodef mailto:security@example.com", "0 custom value with spaces"]),
])
async def test_each_user_record_type_validates_normalizes_and_persists(client, zone, db, record_type, values, expected):
    record = await create(client, zone, record_type=record_type, values=values)
    assert set(record) == FIELDS
    assert record["name"] == "www.example.com" and record["values"] == expected
    assert record["ttl"] == 300 and record["routing_policy"] == "SIMPLE"
    assert record["is_system"] is False and record["alias_target"] is None
    assert (await client.get(path(zone, record["id"]))).json() == record
    db.expire_all()
    assert db.get(DNSRecord, record["id"]).values == expected
    assert (await client.get(BASE + "/" + zone["id"])).json()["record_count"] == 3


@pytest.mark.parametrize("record_type,values", [
    ("A", ["999.1.1.1"]), ("A", ["hello"]), ("A", ["192.168.1"]), ("A", ["2001:db8::1"]),
    ("AAAA", ["192.0.2.1"]), ("AAAA", ["hello"]), ("AAAA", ["fe80::1%eth0"]),
    ("CNAME", ["one.example.com", "two.example.com"]), ("CNAME", ["https://example.com"]), ("CNAME", ["192.0.2.1"]),
    ("CNAME", ["bad..example.com"]), ("MX", ["mail.example.com"]), ("MX", ["-1 mail.example.com"]),
    ("MX", ["65536 mail.example.com"]), ("MX", ["ten mail.example.com"]), ("MX", ["10 https://mail.example.com"]),
    ("NS", ["bad name.com"]), ("NS", ["_ns.example.com"]), ("PTR", ["https://example.com"]), ("PTR", ["192.0.2.1"]),
    ("SRV", ["10 5 service.example.com"]), ("SRV", ["10 5 65536 service.example.com"]),
    ("SRV", ["-1 5 443 service.example.com"]), ("SRV", ["10 -1 443 service.example.com"]),
    ("SRV", ["10 5 443 https://service.example.com"]), ("CAA", ["256 issue letsencrypt.org"]),
    ("CAA", ["-1 issue letsencrypt.org"]), ("CAA", ["0 issue"]), ("CAA", ['0 issue ""']),
    ("CAA", ["0 bad_tag value"]), ("TXT", ['""']), ("SOA", ["ns.example.com hostmaster.example.com 1 2 3 4 5"]),
])
async def test_invalid_type_values_rejected_without_persisting(client, zone, record_type, values):
    response = await client.post(path(zone), json={"name": "www", "record_type": record_type, "values": values})
    assert response.status_code == 422
    assert all(set(issue) == {"type", "loc", "msg"} for issue in response.json()["detail"])
    assert (await client.get(path(zone))).json()["total"] == 2


@pytest.mark.parametrize("override", [
    {"values": []}, {"values": [""]}, {"values": [" "]}, {"values": [123]}, {"values": "192.0.2.1"},
    {"values": ["hello\nworld"]}, {"values": ["x" * 4097]}, {"values": ["192.0.2.1"] * 101},
    {"ttl": 0}, {"ttl": -1}, {"ttl": None}, {"ttl": True}, {"ttl": 3.5}, {"ttl": "300"}, {"ttl": 2147483648},
    {"is_system": True}, {"is_system": False}, {"id": "custom"}, {"hosted_zone_id": "ZOTHER"}, {"owner_id": 1},
    {"created_at": "2026-01-01"}, {"record_type": "UNKNOWN"}, {"routing_policy": "WEIGHTED"},
    {"alias": True}, {"alias": "false"}, {"alias_target": {"dns_name": "target.example.com"}},
])
async def test_invalid_generic_fields_and_privilege_attempts_rejected(client, zone, override):
    response = await client.post(path(zone), json={"name": "www", "record_type": "A", "values": ["192.0.2.1"], **override})
    assert response.status_code == 422
    assert (await client.get(path(zone))).json()["total"] == 2


@pytest.mark.parametrize("name,record_type,expected", [
    (" WWW ", "A", "www.example.com"), ("WWW.Example.COM.", "A", "www.example.com"),
    ("@", "A", "example.com"), ("", "A", "example.com"), ("example.com", "A", "example.com"),
    ("_sip._tcp", "SRV", "_sip._tcp.example.com"), ("_sip._tcp.example.com.", "SRV", "_sip._tcp.example.com"),
    ("_acme-challenge", "TXT", "_acme-challenge.example.com"), ("*", "A", "*.example.com"),
])
async def test_record_owner_name_normalization(client, zone, name, record_type, expected):
    values = ["10 5 443 target.example.com"] if record_type == "SRV" else ["text"] if record_type == "TXT" else ["192.0.2.1"]
    record = await create(client, zone, name=name, record_type=record_type, values=values)
    assert record["name"] == expected


@pytest.mark.parametrize("name,record_type", [
    ("www.google.com", "A"), ("example.com.evil.com", "A"), ("notexample.com", "A"), ("www.", "A"),
    ("https://example.com", "A"), ("bad domain", "A"), ("bad..example.com", "A"), ("-bad", "A"),
    ("bad-", "A"), ("_sip._tcp.example.com", "A"), ("a" * 64, "A"), ("foo.*.example.com", "A"),
    ("@", "CNAME"), ("", "CNAME"), ("EXAMPLE.COM.", "CNAME"),
])
async def test_out_of_zone_malformed_and_apex_cname_names_rejected(client, zone, name, record_type):
    values = ["target.example.net"] if record_type == "CNAME" else ["192.0.2.1"]
    response = await client.post(path(zone), json={"name": name, "record_type": record_type, "values": values})
    assert response.status_code == 422
    assert "name" in response.json()["detail"][0]["loc"]


async def test_deduplicates_canonical_values_preserving_order(client, zone):
    record = await create(client, zone, record_type="AAAA", values=["2001:DB8::1", "2001:db8::2", "2001:0db8::1"])
    assert record["values"] == ["2001:db8::1", "2001:db8::2"]


async def test_uniqueness_across_create_update_type_and_zone(client, zone):
    first = await create(client, zone)
    duplicate = await client.post(path(zone), json={"name": "WWW.Example.COM.", "record_type": "A", "values": ["192.0.2.20"]})
    assert duplicate.status_code == 409 and "already exists" in duplicate.json()["detail"]
    await create(client, zone, record_type="AAAA", values=["2001:db8::1"])
    other = await create(client, zone, name="other")
    assert (await client.patch(path(zone, other["id"]), json={"name": "www"})).status_code == 409
    assert (await client.patch(path(zone, other["id"]), json={"name": "www", "record_type": "AAAA", "values": ["2001:db8::2"]})).status_code == 409
    assert (await client.patch(path(zone, first["id"]), json={"ttl": 600})).status_code == 200
    second = (await client.post(BASE, json={"name": "example.com"})).json()
    assert (await create(client, second))["id"] != first["id"]
    assert (await client.post(path(zone), json={"name": "@", "record_type": "NS", "values": ["ns.provider.com"]})).status_code == 409


async def test_patch_final_state_type_transition_timestamps_and_count(client, zone, db):
    original = await create(client, zone)
    url = path(zone, original["id"])
    updated = await client.patch(url, json={"values": ["192.0.2.20", "192.0.2.30"], "ttl": 600})
    assert updated.status_code == 200
    saved = updated.json()
    assert saved["values"] == ["192.0.2.20", "192.0.2.30"] and saved["ttl"] == 600
    assert datetime.fromisoformat(saved["updated_at"]) > datetime.fromisoformat(original["updated_at"])
    assert saved["created_at"] == original["created_at"] and saved["id"] == original["id"]
    assert (await client.patch(url, json={"record_type": "AAAA"})).status_code == 422
    assert (await client.patch(url, json={"values": ["999.1.1.1"]})).status_code == 422
    assert (await client.get(url)).json() == saved
    transition = await client.patch(url, json={"record_type": "AAAA", "values": ["2001:db8::1"], "name": "ipv6"})
    assert transition.status_code == 200 and transition.json()["name"] == "ipv6.example.com"
    assert (await client.get(BASE + "/" + zone["id"])).json()["record_count"] == 3
    db.expire_all()
    assert db.get(DNSRecord, original["id"]).record_type == DNSRecordType.AAAA


@pytest.mark.parametrize("payload", [{}, {"name": None}, {"values": None}, {"ttl": None}, {"record_type": None},
    {"routing_policy": None}, {"is_system": False}, {"alias": True}, {"record_type": "SOA"}, {"values": []}, {"ttl": 0}])
async def test_invalid_patch_keeps_previous_record(client, zone, payload):
    record = await create(client, zone)
    response = await client.patch(path(zone, record["id"]), json=payload)
    assert response.status_code == 422
    assert (await client.get(path(zone, record["id"]))).json() == record


@pytest.mark.parametrize("kind", ["NS", "SOA"])
@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
async def test_system_records_are_readable_but_cannot_be_mutated(client, zone, kind, method):
    record = next(r for r in (await client.get(path(zone))).json()["items"] if r["record_type"] == kind)
    response = await client.request(method, path(zone, record["id"]), json={"ttl": 600} if method == "PATCH" else None)
    assert response.status_code == 409 and "System-managed" in response.json()["detail"]
    assert (await client.get(path(zone, record["id"]))).json() == record


async def test_delete_count_and_zone_cascade(client, zone, db):
    record = await create(client, zone)
    response = await client.delete(path(zone, record["id"]))
    assert response.status_code == 204 and response.content == b""
    assert response.headers["cache-control"] == "no-store"
    assert (await client.get(BASE + "/" + zone["id"])).json()["record_count"] == 2
    assert (await client.delete(path(zone, record["id"]))).status_code == 404
    assert (await client.get(path(zone, record["id"]))).status_code == 404
    await create(client, zone)
    await create(client, zone, name="other")
    assert (await client.delete(BASE + "/" + zone["id"])).status_code == 204
    assert db.scalar(select(func.count()).select_from(DNSRecord).where(DNSRecord.hosted_zone_id == zone["id"])) == 0


@pytest.mark.parametrize("query", [
    "page=0", "page=-1", "page=2147483648", "page_size=0", "page_size=101", "page_size=no",
    "sort_by=values", "sort_order=sideways", "record_type=INVALID", "system=maybe", "unknown=x",
])
async def test_invalid_list_parameters(client, zone, query):
    assert (await client.get(path(zone) + "?" + query)).status_code == 422


async def test_sql_search_filters_pagination_sort_and_empty_states(client, zone):
    await create(client, zone, name="alpha", values=["192.0.2.10"], ttl=100)
    await create(client, zone, name="beta", values=["192.0.2.20"], ttl=200)
    await create(client, zone, name="token", record_type="TXT", values=["token=AbC_100%", "verification=SecondValue"], ttl=300)
    for query, names in [
        ("search=ALPHA", ["alpha.example.com"]), ("search=192.0.2.20", ["beta.example.com"]),
        ("search=secondvalue", ["token.example.com"]), ("search=%25", ["token.example.com"]),
        ("search=_100", ["token.example.com"]), ("record_type=A&sort_order=desc", ["beta.example.com", "alpha.example.com"]),
        ("record_type=A&sort_by=ttl&sort_order=asc", ["alpha.example.com", "beta.example.com"]),
        ("record_type=A&search=beta", ["beta.example.com"]),
    ]:
        response = await client.get(path(zone) + "?" + query)
        assert response.status_code == 200
        assert [r["name"] for r in response.json()["items"]] == names
    assert (await client.get(path(zone) + "?system=true")).json()["total"] == 2
    assert (await client.get(path(zone) + "?system=false")).json()["total"] == 3
    paged = (await client.get(path(zone) + "?page=2&page_size=2")).json()
    assert (paged["page"], paged["total"], paged["pages"], len(paged["items"])) == (2, 5, 3, 2)
    all_ids = []
    for page in range(1, 4):
        all_ids.extend(r["id"] for r in (await client.get(path(zone) + f"?page={page}&page_size=2")).json()["items"])
    assert len(set(all_ids)) == len(all_ids) == 5
    empty = (await client.get(path(zone) + "?search=missing")).json()
    assert empty["items"] == [] and empty["total"] == empty["pages"] == 0
    beyond = (await client.get(path(zone) + "?page=2147483647&page_size=100")).json()
    assert beyond["items"] == [] and beyond["total"] == 5


@pytest.mark.parametrize("sort_by", ["name", "record_type", "ttl", "created_at", "updated_at"])
@pytest.mark.parametrize("sort_order", ["asc", "desc"])
async def test_sort_whitelist_both_directions(client, zone, sort_by, sort_order):
    await create(client, zone, name="alpha", ttl=600)
    await create(client, zone, name="beta", record_type="AAAA", values=["2001:db8::1"], ttl=100)
    items = (await client.get(path(zone) + f"?sort_by={sort_by}&sort_order={sort_order}")).json()["items"]
    keys = [r[sort_by] for r in items]
    assert keys == sorted(keys, reverse=sort_order == "desc")


@pytest.mark.parametrize("method,payload", [("POST", {"name": "www", "record_type": "A", "values": ["192.0.2.1"]}),
                                          ("PATCH", {"ttl": 600}), ("DELETE", None)])
async def test_writes_preserve_origin_protection(client, zone, method, payload):
    record = await create(client, zone)
    response = await client.request(method, path(zone, None if method == "POST" else record["id"]),
                                    json=payload, headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 403
    assert (await client.get(path(zone, record["id"]))).json() == record


async def test_openapi_documents_nested_routes_cookie_contract_and_readonly_system_fields(client):
    schema = (await client.get("/openapi.json")).json()
    collection = schema["paths"][BASE + "/{zone_id}/records"]
    single = schema["paths"][BASE + "/{zone_id}/records/{record_id}"]
    for operation in [*collection.values(), *single.values()]:
        assert operation["tags"] == ["DNS Records"]
        assert {"SessionCookie": []} in operation["security"]
    assert set(collection) == {"get", "post"} and set(single) == {"get", "patch", "delete"}
    assert "201" in collection["post"]["responses"]
    assert "content" not in single["delete"]["responses"]["204"]
    props = schema["components"]["schemas"]["DNSRecordCreate"]["properties"]
    assert "is_system" not in props and "hosted_zone_id" not in props
    assert set(p["name"] for p in collection["get"]["parameters"]) >= {
        "search", "record_type", "system", "page", "page_size", "sort_by", "sort_order",
    }


async def test_list_uses_bounded_sql_without_loading_zone_records(client, zone, db_engine):
    for index in range(8):
        await create(client, zone, name=f"host{index}")
    statements = []
    def capture(connection, cursor, sql, parameters, context, many):
        if "FROM dns_records" in sql:
            statements.append(sql)
    event.listen(db_engine, "before_cursor_execute", capture)
    try:
        assert (await client.get(path(zone) + "?page_size=1")).status_code == 200
        first = list(statements)
        statements.clear()
        assert (await client.get(path(zone) + "?page_size=100")).status_code == 200
        assert len(first) == len(statements) == 2
        assert "count(*)" in statements[0].lower()
        assert "LIMIT" in statements[1] and "OFFSET" in statements[1] and "ORDER BY" in statements[1]
    finally:
        event.remove(db_engine, "before_cursor_execute", capture)


async def test_database_uniqueness_race_translates_to_conflict_and_session_recovers(client, zone, db, users, monkeypatch):
    record = await create(client, zone)
    other = await create(client, zone, name="other")
    with monkeypatch.context() as patch:
        patch.setattr(service, "ensure_unique", lambda *args, **kwargs: None)
        response = await client.post(path(zone), json={"name": "www", "record_type": "A", "values": ["192.0.2.40"]})
        assert response.status_code == 409
        assert (await client.patch(path(zone, other["id"]), json={"name": "www"})).status_code == 409
        with pytest.raises(service.DNSRecordConflict):
            service.create_record(db, users[0].id, zone["id"], DNSRecordCreate(name="www", record_type="A", values=["192.0.2.20"]))
    assert db.is_active and db.get(DNSRecord, record["id"]).values == ["192.0.2.10"]
    assert (await client.get(path(zone, other["id"]))).json() == other
    assert service.create_record(db, users[0].id, zone["id"], DNSRecordCreate(name="retry", record_type="A", values=["192.0.2.30"]))


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
async def test_write_failure_rolls_back_and_session_recovers(client, zone, db, users, monkeypatch, operation):
    record = await create(client, zone)
    def broken_commit():
        db.flush()
        raise SQLAlchemyError("Controlled transaction failure")
    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", broken_commit)
        with pytest.raises(SQLAlchemyError):
            if operation == "create":
                service.create_record(db, users[0].id, zone["id"], DNSRecordCreate(name="failed", record_type="A", values=["192.0.2.20"]))
            elif operation == "update":
                service.update_record(db, users[0].id, zone["id"], record["id"], DNSRecordUpdate(values=["192.0.2.20"]))
            else:
                service.delete_record(db, users[0].id, zone["id"], record["id"])
    assert db.is_active and db.get(DNSRecord, record["id"]).values == ["192.0.2.10"]
    assert service.list_records(db, users[0].id, zone["id"], DNSRecordListQuery()).total == 3
    assert service.update_record(db, users[0].id, zone["id"], record["id"], DNSRecordUpdate(ttl=600)).ttl == 600


async def test_zone_rename_record_collision_rolls_back_atomically(client, zone, db):
    # Existing internal data can collide with a future apex when a zone is renamed.
    db.add(DNSRecord(hosted_zone_id=zone["id"], name="new.example.com", record_type=DNSRecordType.NS,
                     values=["ns.provider.com."]))
    db.commit()
    response = await client.patch(BASE + "/" + zone["id"], json={"name": "new.example.com"})
    assert response.status_code == 409
    assert (await client.get(BASE + "/" + zone["id"])).json()["name"] == "example.com"
    system = (await client.get(path(zone) + "?system=true")).json()["items"]
    assert {r["name"] for r in system} == {"example.com"}


async def test_numeric_boundaries_and_srv_unavailable_target(client, zone):
    record = await create(client, zone, name="mx", record_type="MX", values=["0 mail.example.com", "65535 backup.example.com"], ttl=2147483647)
    assert record["ttl"] == 2147483647
    assert (await create(client, zone, name="_service._tcp", record_type="SRV", values=["0 65535 65535 ."]))["values"] == ["0 65535 65535 ."]
    assert (await create(client, zone, name="caa", record_type="CAA", values=["255 custom value"]))["values"] == ["255 custom value"]


async def test_normalized_owner_total_length_is_checked_after_appending_zone(client, zone):
    long_zone = ".".join(["a" * 63, "b" * 63, "c" * 63, "d" * 48])
    created = await client.post(BASE, json={"name": long_zone})
    assert created.status_code == 201
    response = await client.post(path(created.json()), json={"name": "x" * 63, "record_type": "A", "values": ["192.0.2.1"]})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "name"]


async def test_each_crud_operation_commits_once(client, zone, db, users):
    commits = []
    def committed(session):
        commits.append(True)
    event.listen(db, "after_commit", committed)
    try:
        record = service.create_record(db, users[0].id, zone["id"], DNSRecordCreate(name="one", record_type="A", values=["192.0.2.1"]))
        assert len(commits) == 1
        service.update_record(db, users[0].id, zone["id"], record.id, DNSRecordUpdate(ttl=600))
        assert len(commits) == 2
        service.delete_record(db, users[0].id, zone["id"], record.id)
        assert len(commits) == 3
    finally:
        event.remove(db, "after_commit", committed)
