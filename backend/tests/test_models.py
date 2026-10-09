from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session as ORMSession

from app.models import DNSRecord, HostedZone, Session, User
from app.models.enums import DNSRecordType, RoutingPolicy, ZoneType
from app.schemas.dns_record import DNSRecordRead
from app.schemas.auth import AuthUserResponse
from app.services.hosted_zone_service import get_hosted_zone


@pytest.fixture
def user(db: ORMSession) -> User:
    owner = User(email="owner@example.test", display_name="Test owner", password_hash="test-only-hash")
    db.add(owner)
    db.commit()
    return owner


@pytest.fixture
def zone(db: ORMSession, user: User) -> HostedZone:
    hosted_zone = HostedZone(id="Z0123456789ABCDEF", owner=user, name="example.com")
    db.add(hosted_zone)
    db.commit()
    return hosted_zone


def new_record(zone: HostedZone, **overrides: object) -> DNSRecord:
    fields: dict[str, object] = {
        "hosted_zone": zone,
        "name": "example.com",
        "record_type": DNSRecordType.A,
        "values": ["192.0.2.1", "192.0.2.2"],
    }
    fields.update(overrides)
    return DNSRecord(**fields)


def row_count(db: ORMSession, model: type[User | Session | HostedZone | DNSRecord]) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_user_creation_and_safe_response(db: ORMSession, user: User) -> None:
    db.expire_all()
    saved = db.get(User, user.id)
    assert saved is not None
    assert saved.email == "owner@example.test"
    assert saved.is_active is True
    assert saved.created_at.tzinfo == UTC
    assert saved.updated_at.tzinfo == UTC
    response = AuthUserResponse.model_validate(saved).model_dump()
    assert response["display_name"] == "Test owner"
    assert "password_hash" not in response


def test_database_defaults_without_orm_insert(db: ORMSession) -> None:
    db.execute(
        text("INSERT INTO users (email, display_name, password_hash) "
             "VALUES ('sql@example.test', 'SQL test', 'test-only-hash')")
    )
    owner_id = db.scalar(text("SELECT id FROM users WHERE email = 'sql@example.test'"))
    db.execute(
        text("INSERT INTO hosted_zones (id, owner_id, name) "
             "VALUES ('ZRAW', :owner_id, 'example.test')"),
        {"owner_id": owner_id},
    )
    record_id = "00000000-0000-4000-8000-000000000001"
    db.execute(
        text("INSERT INTO dns_records (id, hosted_zone_id, name, record_type) "
             "VALUES (:id, 'ZRAW', 'example.test', 'A')"),
        {"id": record_id},
    )
    db.commit()
    owner = db.get(User, owner_id)
    zone = db.get(HostedZone, "ZRAW")
    record = db.get(DNSRecord, record_id)
    assert owner is not None and zone is not None and record is not None
    assert owner.is_active is True
    assert owner.created_at.tzinfo == owner.updated_at.tzinfo == UTC
    assert zone.zone_type is ZoneType.PUBLIC
    assert record.values == [] and record.ttl == 300
    assert record.routing_policy is RoutingPolicy.SIMPLE
    assert record.alias is False and record.is_system is False
    assert record.created_at.tzinfo == record.updated_at.tzinfo == UTC


def test_relationships_values_and_defaults(db: ORMSession, zone: HostedZone) -> None:
    record = new_record(zone)
    db.add(record)
    db.commit()
    record_id, zone_id, owner_id = record.id, zone.id, zone.owner_id
    db.expunge_all()
    saved = db.get(DNSRecord, record_id)
    assert saved is not None
    assert UUID(saved.id).version == 4
    assert saved.values == ["192.0.2.1", "192.0.2.2"]
    assert saved.ttl == 300
    assert saved.routing_policy == RoutingPolicy.SIMPLE
    assert saved.alias is False
    assert saved.alias_target is None
    assert saved.is_system is False
    assert saved.hosted_zone.id == zone_id
    assert saved.hosted_zone.owner.id == owner_id
    assert saved in saved.hosted_zone.records
    assert saved.hosted_zone in saved.hosted_zone.owner.hosted_zones
    assert get_hosted_zone(db, owner_id, zone_id).id == zone_id
    assert DNSRecordRead.model_validate(saved).values == saved.values


def test_duplicate_zone_names(db: ORMSession, zone: HostedZone) -> None:
    second = HostedZone(id="Z089XYZ123456ABC", owner=zone.owner, name=zone.name)
    db.add(second)
    db.commit()
    assert row_count(db, HostedZone) == 2


@pytest.mark.parametrize("record_type", list(DNSRecordType))
def test_all_record_types(db: ORMSession, zone: HostedZone, record_type: DNSRecordType) -> None:
    record = new_record(
        zone, record_type=record_type,
        is_system=record_type in {DNSRecordType.NS, DNSRecordType.SOA},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    assert record.record_type is record_type
    assert record.is_system == (record_type in {DNSRecordType.NS, DNSRecordType.SOA})


@pytest.mark.parametrize("ttl", [0, -1])
def test_invalid_ttl_is_rejected(db: ORMSession, zone: HostedZone, ttl: int) -> None:
    db.add(new_record(zone, ttl=ttl))
    with pytest.raises(IntegrityError, match="positive_ttl"):
        db.commit()
    db.rollback()


def test_alias_null_ttl_and_json_mutation(db: ORMSession, zone: HostedZone) -> None:
    record = new_record(
        zone, ttl=None, alias=True, values=[],
        alias_target={"dns_name": "example.elb.amazonaws.com", "hosted_zone_id": "ZTARGET"},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    assert record.ttl is None
    assert record.alias is True
    assert record.alias_target is not None
    record.alias_target["dns_name"] = "updated.elb.amazonaws.com"
    db.commit()
    db.refresh(record)
    assert record.alias_target["dns_name"] == "updated.elb.amazonaws.com"


def test_values_defaults_are_independent_and_mutations_persist(db: ORMSession, zone: HostedZone) -> None:
    first = DNSRecord(hosted_zone=zone, name="first.example.com", record_type=DNSRecordType.A)
    second = DNSRecord(hosted_zone=zone, name="second.example.com", record_type=DNSRecordType.A)
    db.add_all([first, second])
    db.commit()
    first.values.append("192.0.2.3")
    db.commit()
    db.refresh(first)
    db.refresh(second)
    assert first.values == ["192.0.2.3"]
    assert second.values == []


@pytest.mark.parametrize("delete_mode", ["orm_loaded", "orm_unloaded", "sql"])
def test_zone_deletion_cascades(db: ORMSession, zone: HostedZone, delete_mode: str) -> None:
    db.add(new_record(zone))
    db.commit()
    zone_id = zone.id
    assert db.scalar(text("PRAGMA foreign_keys")) == 1
    if delete_mode == "sql":
        db.execute(text("DELETE FROM hosted_zones WHERE id = :id"), {"id": zone_id})
    else:
        db.expunge_all()
        parent = db.get(HostedZone, zone_id)
        assert parent is not None
        if delete_mode == "orm_loaded":
            assert len(parent.records) == 1
        db.delete(parent)
    db.commit()
    db.expunge_all()
    assert row_count(db, DNSRecord) == 0
    assert row_count(db, HostedZone) == 0
    assert row_count(db, User) == 1


@pytest.mark.parametrize("delete_mode", ["orm_loaded", "orm_unloaded", "sql"])
def test_user_deletion_cascades(db: ORMSession, zone: HostedZone, delete_mode: str) -> None:
    owner = zone.owner
    db.add_all([
        new_record(zone),
        Session(user=owner, token_hash="test-token-hash",
                expires_at=datetime(2030, 1, 1, tzinfo=UTC)),
    ])
    db.commit()
    owner_id = owner.id
    if delete_mode == "sql":
        db.execute(text("DELETE FROM users WHERE id = :id"), {"id": owner_id})
    else:
        db.expunge_all()
        parent = db.get(User, owner_id)
        assert parent is not None
        if delete_mode == "orm_loaded":
            assert len(parent.sessions) == 1
            assert len(parent.hosted_zones) == 1
            assert len(parent.hosted_zones[0].records) == 1
        db.delete(parent)
    db.commit()
    db.expunge_all()
    for model in [User, Session, HostedZone, DNSRecord]:
        assert row_count(db, model) == 0


def test_delete_orphan_cascade(db: ORMSession, zone: HostedZone) -> None:
    owner = zone.owner
    record = new_record(zone)
    db.add(record)
    login_session = Session(
        user=owner, token_hash="orphan-hash",
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    db.add_all([record, login_session])
    db.commit()
    zone.records.remove(record)
    zone.owner.sessions.remove(login_session)
    db.commit()
    assert row_count(db, DNSRecord) == row_count(db, Session) == 0


@pytest.mark.parametrize("vpc_id,region", [(None, None), ("vpc-test", None), (None, "ap-south-1"), ("", "ap-south-1"), ("vpc-test", "  ")])
def test_private_zone_requires_vpc(db: ORMSession, user: User, vpc_id: str | None, region: str | None) -> None:
    db.add(HostedZone(
        id="ZPRIVATE", owner=user, name="internal.example",
        zone_type=ZoneType.PRIVATE, vpc_id=vpc_id, region=region,
    ))
    with pytest.raises(IntegrityError, match="private_zone_vpc"):
        db.commit()
    db.rollback()


def test_private_zone_creation(db: ORMSession, user: User) -> None:
    private = HostedZone(
        id="ZPRIVATE", owner=user, name="internal.example",
        zone_type=ZoneType.PRIVATE, vpc_id="vpc-0123456789abcdef", region="ap-south-1",
    )
    db.add(private)
    db.commit()
    db.refresh(private)
    assert private.zone_type is ZoneType.PRIVATE


@pytest.mark.parametrize("column,value", [("record_type", "INVALID"), ("routing_policy", "INVALID"), ("values", "{}"), ("values", "null")])
def test_record_constraints_reject_raw_sql(db: ORMSession, zone: HostedZone, column: str, value: str) -> None:
    record = new_record(zone)
    db.add(record)
    db.commit()
    # Column names come only from this test's fixed parameter list.
    with pytest.raises(IntegrityError):
        db.execute(text(f'UPDATE dns_records SET "{column}" = :value WHERE id = :id'), {"value": value, "id": record.id})
    db.rollback()


def test_invalid_enum_rejected_by_orm_and_database(db: ORMSession, zone: HostedZone) -> None:
    db.add(new_record(zone, record_type="INVALID"))
    with pytest.raises(StatementError):
        db.commit()
    db.rollback()
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE hosted_zones SET zone_type = 'INVALID' WHERE id = :id"), {"id": zone.id})
    db.rollback()


def test_foreign_keys_on_multiple_connections(db_engine: Engine) -> None:
    with db_engine.connect() as first, db_engine.connect() as second:
        assert first.scalar(text("PRAGMA foreign_keys")) == 1
        assert second.scalar(text("PRAGMA foreign_keys")) == 1
        with pytest.raises(IntegrityError):
            second.execute(text("INSERT INTO hosted_zones (id, owner_id, name) VALUES ('ZORPHAN', 999, 'orphan.example')"))


def test_unique_credentials(db: ORMSession, user: User) -> None:
    db.add(User(email=user.email, display_name="Duplicate", password_hash="test-only-hash"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    expires = datetime(2030, 1, 1, tzinfo=UTC)
    db.add_all([
        Session(user=user, token_hash="duplicate-hash", expires_at=expires),
        Session(user=user, token_hash="duplicate-hash", expires_at=expires),
    ])
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_session_uuid_and_utc(db: ORMSession, user: User) -> None:
    expires = datetime(2030, 1, 1, 12, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    login_session = Session(user=user, token_hash="private-test-hash", expires_at=expires)
    db.add(login_session)
    db.commit()
    db.refresh(login_session)
    assert UUID(login_session.id).version == 4
    assert login_session.expires_at == expires.astimezone(UTC)
    assert login_session.expires_at.tzinfo == UTC
    assert login_session.created_at.tzinfo == UTC
    assert login_session.last_seen_at is None


def test_naive_timestamps_are_rejected(db: ORMSession, user: User) -> None:
    db.add(Session(user=user, token_hash="naive-test-hash", expires_at=datetime(2030, 1, 1)))
    with pytest.raises(StatementError, match="timezone-aware"):
        db.commit()
    db.rollback()


def test_updated_at_changes_with_mutations(db: ORMSession, zone: HostedZone) -> None:
    past = datetime(2000, 1, 1, tzinfo=UTC)
    owner = zone.owner
    record = new_record(zone, created_at=past, updated_at=past)
    db.add(record)
    zone.updated_at = past
    owner.updated_at = past
    db.commit()
    record.values.append("192.0.2.4")
    zone.comment = "Updated comment"
    owner.display_name = "Updated owner"
    db.commit()
    for entity in [record, zone, owner]:
        db.refresh(entity)
        assert entity.updated_at > past
        assert entity.updated_at.tzinfo == UTC
    assert record.created_at == past
