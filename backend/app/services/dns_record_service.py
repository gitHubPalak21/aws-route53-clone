"""Owner-scoped record CRUD; HTTP-independent validation and transaction handling."""

from pydantic import ValidationError
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.types import utc_now
from app.models import DNSRecord, HostedZone
from app.schemas.dns_record import (
    DNSRecordCreate, DNSRecordListQuery, DNSRecordListResponse, DNSRecordResponse,
    DNSRecordSortField, DNSRecordUpdate,
)
from app.schemas.hosted_zone import SortOrder
from app.services.dns_validation import normalize_record_name
from app.services.hosted_zone_service import commit_change, owned_zone

EDITABLE_FIELDS = ("name", "record_type", "values", "ttl", "routing_policy")
SORT_COLUMNS = {
    DNSRecordSortField.NAME: DNSRecord.name,
    DNSRecordSortField.RECORD_TYPE: DNSRecord.record_type,
    DNSRecordSortField.TTL: DNSRecord.ttl,
    DNSRecordSortField.CREATED_AT: DNSRecord.created_at,
    DNSRecordSortField.UPDATED_AT: DNSRecord.updated_at,
}


class DNSRecordNotFound(Exception):
    pass


class DNSRecordConflict(Exception):
    pass


class DNSRecordInvalid(Exception):
    def __init__(self, errors: list[dict]) -> None:
        super().__init__("Invalid resulting DNS record")
        self.errors = errors


def owned_record(db: Session, owner_id: int, zone_id: str, record_id: str) -> tuple[DNSRecord, HostedZone]:
    zone = owned_zone(db, owner_id, zone_id)
    record = db.scalar(select(DNSRecord).where(
        DNSRecord.hosted_zone_id == zone_id, DNSRecord.id == record_id,
    ))
    if record is None:
        raise DNSRecordNotFound
    return record, zone


def list_records(db: Session, owner_id: int, zone_id: str, query: DNSRecordListQuery) -> DNSRecordListResponse:
    owned_zone(db, owner_id, zone_id)
    filters = [DNSRecord.hosted_zone_id == zone_id]
    if query.record_type is not None:
        filters.append(DNSRecord.record_type == query.record_type)
    if query.system is not None:
        filters.append(DNSRecord.is_system == query.system)
    if query.search:
        filters.append(or_(DNSRecord.name.icontains(query.search, autoescape=True),
                           cast(DNSRecord.values, String).icontains(query.search, autoescape=True)))
    total = db.scalar(select(func.count()).select_from(DNSRecord).where(*filters)) or 0
    column = SORT_COLUMNS[query.sort_by]
    order = column.asc() if query.sort_order == SortOrder.ASC else column.desc()
    rows = db.scalars(select(DNSRecord).where(*filters)
                      .order_by(order, DNSRecord.record_type.asc(), DNSRecord.id.asc())
                      .limit(query.page_size).offset((query.page - 1) * query.page_size)).all()
    return DNSRecordListResponse(
        items=[DNSRecordResponse.model_validate(row) for row in rows], page=query.page,
        page_size=query.page_size, total=total, pages=(total + query.page_size - 1) // query.page_size,
    )


def get_record(db: Session, owner_id: int, zone_id: str, record_id: str) -> DNSRecordResponse:
    record, _ = owned_record(db, owner_id, zone_id, record_id)
    return DNSRecordResponse.model_validate(record)


def validate_result(fields: dict, zone_name: str) -> DNSRecordCreate:
    try:
        result = DNSRecordCreate.model_validate(fields)
    except ValidationError as exc:
        raise DNSRecordInvalid(exc.errors(include_input=False, include_context=False, include_url=False)) from exc
    try:
        result.name = normalize_record_name(result.name, zone_name, result.record_type)
    except ValueError as exc:
        raise DNSRecordInvalid([{"type": "value_error", "loc": ("name",), "msg": str(exc)}]) from exc
    return result


def ensure_unique(db: Session, zone_id: str, payload: DNSRecordCreate, exclude_id: str | None = None) -> None:
    statement = select(DNSRecord.id).where(
        DNSRecord.hosted_zone_id == zone_id, DNSRecord.name == payload.name,
        DNSRecord.record_type == payload.record_type,
    )
    if exclude_id is not None:
        statement = statement.where(DNSRecord.id != exclude_id)
    if db.scalar(statement) is not None:
        raise DNSRecordConflict(f"{payload.record_type.value} record for {payload.name} already exists")


def save_record(db: Session, record: DNSRecord) -> DNSRecordResponse:
    try:
        commit_change(db)
    except IntegrityError as exc:
        # Translate only the known record-set unique key; unrelated corruption stays an error.
        if "UNIQUE constraint failed: dns_records.hosted_zone_id, dns_records.name, dns_records.record_type" in str(exc.orig):
            raise DNSRecordConflict("A record set with this name and type already exists") from None
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(record)
    return DNSRecordResponse.model_validate(record)


def create_record(db: Session, owner_id: int, zone_id: str, payload: DNSRecordCreate) -> DNSRecordResponse:
    zone = owned_zone(db, owner_id, zone_id)
    validated = validate_result(payload.model_dump(), zone.name)
    ensure_unique(db, zone_id, validated)
    record = DNSRecord(hosted_zone_id=zone_id, is_system=False, **validated.model_dump())
    db.add(record)
    return save_record(db, record)


def update_record(db: Session, owner_id: int, zone_id: str, record_id: str, payload: DNSRecordUpdate) -> DNSRecordResponse:
    record, zone = owned_record(db, owner_id, zone_id, record_id)
    if record.is_system:
        raise DNSRecordConflict("System-managed DNS records cannot be modified")
    fields = {field: getattr(record, field) for field in EDITABLE_FIELDS}
    fields.update(payload.model_dump(exclude_unset=True))
    validated = validate_result(fields, zone.name)
    ensure_unique(db, zone_id, validated, exclude_id=record_id)
    for field in EDITABLE_FIELDS:
        setattr(record, field, getattr(validated, field))
    record.updated_at = utc_now()
    return save_record(db, record)


def delete_record(db: Session, owner_id: int, zone_id: str, record_id: str) -> None:
    record, _ = owned_record(db, owner_id, zone_id, record_id)
    if record.is_system:
        raise DNSRecordConflict("System-managed DNS records cannot be deleted")
    db.delete(record)
    try:
        commit_change(db)
    except Exception:
        db.rollback()
        raise
