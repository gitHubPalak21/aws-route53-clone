"""System defaults against migrated SQLite, including real transaction failures."""

import re
from uuid import UUID

import pytest
from sqlalchemy import event, func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import DNSRecord, HostedZone, User
from app.models.enums import DNSRecordType, RoutingPolicy, ZoneType
from app.schemas.hosted_zone import HostedZoneCreate, HostedZoneListQuery, HostedZoneUpdate
from app.services import hosted_zone_service as zones
from app.services import system_record_service as defaults


@pytest.fixture
def owner(db: Session) -> User:
    user = User(email="system@example.com", display_name="System tests", password_hash="test-only-hash")
    db.add(user)
    db.commit()
    return user


def records(db: Session, zone_id: str) -> list[DNSRecord]:
    return list(db.scalars(select(DNSRecord).where(DNSRecord.hosted_zone_id == zone_id)))


def snapshot(db: Session, zone_id: str) -> dict:
    return {record.id: (record.name, record.record_type, list(record.values), record.ttl,
                        record.created_at, record.updated_at)
            for record in records(db, zone_id)}


@pytest.mark.parametrize("zone_type", [ZoneType.PUBLIC, ZoneType.PRIVATE])
def test_persisted_system_pair_and_derived_counts(db: Session, db_engine: Engine, owner: User, zone_type: ZoneType) -> None:
    private = {"region": "ap-south-1", "vpc_id": "vpc-0123456789abcdef"} if zone_type == ZoneType.PRIVATE else {}
    zone = zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name=" Example.COM. ", zone_type=zone_type, **private))
    assert zone.record_count == 2
    assert zones.get_hosted_zone(db, owner.id, zone.id).record_count == 2
    assert zones.list_hosted_zones(db, owner.id, HostedZoneListQuery()).items[0].record_count == 2

    # A new session reads persisted rows, not an in-memory relationship.
    with Session(db_engine) as fresh:
        saved = records(fresh, zone.id)
        assert len(saved) == 2
        by_type = {record.record_type: record for record in saved}
        assert set(by_type) == {DNSRecordType.NS, DNSRecordType.SOA}
        for record in saved:
            assert UUID(record.id).version == 4
            assert record.name == zone.name == "example.com"
            assert record.hosted_zone_id == zone.id
            assert record.is_system is True and record.alias is False
            assert record.alias_target is None and record.routing_policy == RoutingPolicy.SIMPLE
        ns, soa = by_type[DNSRecordType.NS], by_type[DNSRecordType.SOA]
        assert ns.ttl == 172800 and len(ns.values) == len(set(ns.values)) == 4
        assert soa.ttl == 900 and len(soa.values) == 1
        assert soa.values[0].split() == [ns.values[0], "awsdns-hostmaster.amazon.com.",
                                       "1", "7200", "900", "1209600", "86400"]
        assert "record_count" not in HostedZone.__table__.columns


def test_mock_nameservers_have_four_unique_absolute_dns_families() -> None:
    for _ in range(20):
        values = defaults.generate_mock_nameservers()
        assert len(values) == len(set(values)) == 4
        matches = [re.fullmatch(r"ns-(\d+)\.awsdns-(\d{2})\.(com|net|org|co\.uk)\.", value)
                   for value in values]
        assert all(matches)
        assert {match.group(3) for match in matches} == {"com", "net", "org", "co.uk"}
        assert all(1 <= int(match.group(1)) <= 2048 for match in matches)
        assert all(0 <= int(match.group(2)) <= 63 for match in matches)


def test_factory_repeated_before_and_after_flush_does_not_duplicate(db: Session, db_engine: Engine, owner: User, monkeypatch: pytest.MonkeyPatch) -> None:
    zone = HostedZone(id="ZFACTORY", owner_id=owner.id, name="factory.example.com")
    db.add(zone)
    defaults.add_default_system_records(zone)
    assert len(zone.records) == 2

    def unexpected_generation():
        raise AssertionError("Existing nameservers must not be regenerated")

    monkeypatch.setattr(defaults, "generate_mock_nameservers", unexpected_generation)
    defaults.add_default_system_records(zone)
    db.commit()
    original = snapshot(db, zone.id)
    with Session(db_engine) as fresh:
        defaults.add_default_system_records(fresh.get(HostedZone, zone.id))
        fresh.commit()
        assert snapshot(fresh, zone.id) == original


@pytest.mark.parametrize("types", [(DNSRecordType.NS,), (DNSRecordType.NS, DNSRecordType.NS, DNSRecordType.SOA)])
def test_factory_rejects_inconsistent_existing_pair(db: Session, owner: User, types: tuple) -> None:
    zone = HostedZone(id="ZINCONSISTENT", owner_id=owner.id, name="factory.example.com")
    zone.records = [DNSRecord(name=zone.name, record_type=kind, is_system=True) for kind in types]
    db.add(zone)
    with pytest.raises(ValueError, match="incomplete or duplicated"):
        defaults.add_default_system_records(zone)
    assert len(zone.records) == len(types)
    db.rollback()


def test_duplicate_zone_names_have_separate_record_ids_and_values_lists(db: Session, owner: User) -> None:
    first = zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="example.com"))
    second = zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="EXAMPLE.COM."))
    a, b = records(db, first.id), records(db, second.id)
    assert first.id != second.id and first.name == second.name
    assert len(a) == len(b) == 2 and len({record.id for record in a + b}) == 4
    a_ns = next(record for record in a if record.record_type == DNSRecordType.NS)
    b_ns = next(record for record in b if record.record_type == DNSRecordType.NS)
    original_b = list(b_ns.values)
    a_ns.values.append("extra.test.invalid.")
    db.commit()
    db.expire_all()
    assert b_ns.values == original_b
    assert all(record.hosted_zone_id == first.id for record in a)
    assert all(record.hosted_zone_id == second.id for record in b)


@pytest.mark.parametrize("zone_type", [ZoneType.PUBLIC, ZoneType.PRIVATE])
def test_updates_never_generate_more_records(db: Session, owner: User, monkeypatch: pytest.MonkeyPatch, zone_type: ZoneType) -> None:
    private = {"region": "ap-south-1", "vpc_id": "vpc-0123456789abcdef"} if zone_type == ZoneType.PRIVATE else {}
    zone = zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="example.com", zone_type=zone_type, **private))
    original = snapshot(db, zone.id)

    def unexpected_factory(_zone):
        raise AssertionError("Updates must not create system records")

    monkeypatch.setattr(zones, "add_default_system_records", unexpected_factory)
    updates = [
        HostedZoneUpdate(comment="Changed"),
        HostedZoneUpdate(zone_type=zone_type),
        HostedZoneUpdate(name="EXAMPLE.COM."),
    ]
    if zone_type == ZoneType.PRIVATE:
        updates.append(HostedZoneUpdate(region="us-east-1", vpc_id="vpc-12345678"))
    for payload in updates:
        assert zones.update_hosted_zone(db, owner.id, zone.id, payload).record_count == 2
        assert snapshot(db, zone.id) == original

    current = zones.get_hosted_zone(db, owner.id, zone.id)
    opposite = ZoneType.PRIVATE if zone_type == ZoneType.PUBLIC else ZoneType.PUBLIC
    with pytest.raises(zones.HostedZoneTypeImmutable):
        zones.update_hosted_zone(db, owner.id, zone.id, HostedZoneUpdate(zone_type=opposite))
    assert zones.get_hosted_zone(db, owner.id, zone.id) == current
    assert snapshot(db, zone.id) == original


def test_rename_only_updates_system_apex_names_and_preserves_dns_data(db: Session, owner: User) -> None:
    zone = zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="example.com"))
    extra = [DNSRecord(hosted_zone_id=zone.id, name="delegation.example.com", record_type=kind,
                       values=["user-or-other-system-value"], is_system=kind == DNSRecordType.TXT)
             for kind in [DNSRecordType.NS, DNSRecordType.SOA, DNSRecordType.A, DNSRecordType.TXT]]
    db.add_all(extra)
    db.commit()
    before = snapshot(db, zone.id)
    system_ids = {record.id for record in records(db, zone.id)
                  if record.is_system and record.record_type in {DNSRecordType.NS, DNSRecordType.SOA}}
    result = zones.update_hosted_zone(db, owner.id, zone.id, HostedZoneUpdate(name=" EXAMPLE.ORG. "))
    after = snapshot(db, zone.id)
    assert result.name == "example.org" and result.record_count == 6
    assert before.keys() == after.keys()
    for record_id, old in before.items():
        new = after[record_id]
        if record_id in system_ids:
            assert new[0] == "example.org" and new[1:5] == old[1:5]
            assert new[5] >= old[5]
        else:
            assert new == old


@pytest.mark.parametrize("stage", ["system-update", "commit"])
def test_rename_failure_rolls_back_zone_and_system_names(db: Session, owner: User, monkeypatch: pytest.MonkeyPatch, stage: str) -> None:
    zone = zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="example.com"))
    before = snapshot(db, zone.id)
    real_sync = zones.synchronize_system_record_names

    def broken_sync(session, resource):
        real_sync(session, resource)
        session.flush()
        raise RuntimeError("Rename probe")

    def broken_commit():
        db.flush()
        raise SQLAlchemyError("Rename probe")

    with monkeypatch.context() as patch:
        if stage == "system-update":
            patch.setattr(zones, "synchronize_system_record_names", broken_sync)
        else:
            patch.setattr(db, "commit", broken_commit)
        with pytest.raises((RuntimeError, SQLAlchemyError), match="Rename probe"):
            zones.update_hosted_zone(db, owner.id, zone.id, HostedZoneUpdate(name="example.org"))
    assert db.is_active
    assert zones.get_hosted_zone(db, owner.id, zone.id) == zone
    assert snapshot(db, zone.id) == before
    assert zones.update_hosted_zone(db, owner.id, zone.id, HostedZoneUpdate(name="retry.example.org")).record_count == 2


@pytest.mark.parametrize("kind", [DNSRecordType.NS, DNSRecordType.SOA])
def test_record_insert_failure_rolls_back_all_rows_and_session_recovers(db: Session, owner: User, kind: DNSRecordType) -> None:
    seen = []

    def fail_after_insert(mapper, connection, record):
        if record.record_type == kind:
            # The INSERTs have really reached SQLite inside the uncommitted transaction.
            seen.append(connection.scalar(select(func.count()).select_from(DNSRecord)))
            raise RuntimeError("System insert probe")

    event.listen(DNSRecord, "after_insert", fail_after_insert)
    try:
        with pytest.raises(RuntimeError, match="System insert probe"):
            zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="failed.example.com"))
    finally:
        event.remove(DNSRecord, "after_insert", fail_after_insert)
    assert seen and seen[0] > 0 and db.is_active
    assert db.scalar(select(func.count()).select_from(HostedZone)) == 0
    assert db.scalar(select(func.count()).select_from(DNSRecord)) == 0
    assert zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="retry.example.com")).record_count == 2


def test_generation_failure_clears_pending_zone(db: Session, owner: User, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_generation():
        raise ValueError("Generation probe")

    with monkeypatch.context() as patch:
        patch.setattr(defaults, "generate_mock_nameservers", fail_generation)
        with pytest.raises(ValueError, match="Generation probe"):
            zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="failed.example.com"))
    assert not db.new and db.is_active
    assert db.scalar(select(func.count()).select_from(HostedZone)) == 0
    assert db.scalar(select(func.count()).select_from(DNSRecord)) == 0
    assert zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="retry.example.com")).record_count == 2


def test_successful_create_commits_once(db: Session, owner: User) -> None:
    commits = []

    def committed(session):
        commits.append(True)

    event.listen(db, "after_commit", committed)
    try:
        zone = zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="example.com"))
    finally:
        event.remove(db, "after_commit", committed)
    assert commits == [True] and len(records(db, zone.id)) == 2


def test_delete_uses_database_cascade_for_unloaded_system_records(db: Session, db_engine: Engine, owner: User) -> None:
    zone = zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="example.com"))
    owner_id = owner.id
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    with Session(db_engine) as fresh:
        resource = fresh.get(HostedZone, zone.id)
        assert "records" in inspect(resource).unloaded
        assert len(records(fresh, zone.id)) == 2
        event.listen(db_engine, "before_cursor_execute", capture)
        try:
            zones.delete_hosted_zone(fresh, owner_id, zone.id)
        finally:
            event.remove(db_engine, "before_cursor_execute", capture)
        assert records(fresh, zone.id) == [] and fresh.get(HostedZone, zone.id) is None
    assert not any(sql.lstrip().upper().startswith("DELETE FROM DNS_RECORDS") for sql in statements)


def test_other_owner_cannot_read_rename_or_delete_system_zone(db: Session, owner: User) -> None:
    zone = zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="example.com"))
    before = snapshot(db, zone.id)
    other = User(email="other@example.com", display_name="Other", password_hash="test-only-hash")
    db.add(other)
    db.commit()
    assert zones.list_hosted_zones(db, other.id, HostedZoneListQuery()).items == []
    with pytest.raises(zones.HostedZoneNotFound):
        zones.get_hosted_zone(db, other.id, zone.id)
    with pytest.raises(zones.HostedZoneNotFound):
        zones.update_hosted_zone(db, other.id, zone.id, HostedZoneUpdate(name="stolen.example.com"))
    with pytest.raises(zones.HostedZoneNotFound):
        zones.delete_hosted_zone(db, other.id, zone.id)
    assert snapshot(db, zone.id) == before


def test_historical_zones_unchanged_by_startup_and_updates(db: Session, owner: User) -> None:
    legacy = HostedZone(id="ZLEGACY", owner_id=owner.id, name="legacy.example.com")
    db.add(legacy)
    db.commit()
    create_app()
    new = zones.create_hosted_zone(db, owner.id, HostedZoneCreate(name="new.example.com"))
    assert zones.update_hosted_zone(db, owner.id, legacy.id, HostedZoneUpdate(name="renamed-legacy.example.com", comment="Legacy")).record_count == 0
    assert records(db, legacy.id) == []
    assert {item.id: item.record_count for item in zones.list_hosted_zones(db, owner.id, HostedZoneListQuery()).items} == {legacy.id: 0, new.id: 2}


def test_system_creation_stays_on_zone_endpoint() -> None:
    paths = create_app().openapi()["paths"]
    assert {path for path in paths if "records" in path} == {
        "/api/hosted-zones/{zone_id}/records", "/api/hosted-zones/{zone_id}/records/{record_id}",
    }
    assert "mocked NS and SOA" in paths["/api/hosted-zones"]["post"]["summary"]
