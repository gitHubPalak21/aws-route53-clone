"""Owner-scoped hosted-zone operations, independent of HTTP handling."""

import secrets
import string

from pydantic import ValidationError
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.types import utc_now
from app.models import DNSRecord, HostedZone
from app.models.enums import ZoneType
from app.schemas.hosted_zone import (
    HostedZoneCreate, HostedZoneListQuery, HostedZoneListResponse,
    HostedZoneResponse, HostedZoneSortField, HostedZoneUpdate, SortOrder,
)
from app.services.system_record_service import add_default_system_records, synchronize_system_record_names

ID_ATTEMPTS = 5
EDITABLE_FIELDS = ("name", "comment", "zone_type", "vpc_id", "region")
SORT_COLUMNS = {
    HostedZoneSortField.NAME: HostedZone.name,
    HostedZoneSortField.ZONE_TYPE: HostedZone.zone_type,
    HostedZoneSortField.CREATED_AT: HostedZone.created_at,
    HostedZoneSortField.UPDATED_AT: HostedZone.updated_at,
    HostedZoneSortField.ID: HostedZone.id,
}


class HostedZoneNotFound(Exception):
    pass


class HostedZoneIDUnavailable(Exception):
    pass


class HostedZoneRecordConflict(Exception):
    pass


class HostedZoneUpdateInvalid(Exception):
    def __init__(self, validation_error: ValidationError) -> None:
        super().__init__("Invalid resulting hosted zone")
        self.errors = validation_error.errors(include_input=False, include_context=False, include_url=False)


def generate_hosted_zone_id() -> str:
    """Z plus 20 uniformly sampled uppercase alphanumerics (~103 random bits)."""
    alphabet = string.ascii_uppercase + string.digits
    return "Z" + "".join(secrets.choice(alphabet) for _ in range(20))


def response_query() -> Select:
    record_count = (
        select(func.count(DNSRecord.id))
        .where(DNSRecord.hosted_zone_id == HostedZone.id)
        .correlate(HostedZone).scalar_subquery().label("record_count")
    )
    return select(
        HostedZone.id, HostedZone.name, HostedZone.comment, HostedZone.zone_type,
        HostedZone.vpc_id, HostedZone.region, record_count,
        HostedZone.created_at, HostedZone.updated_at,
    )


def list_hosted_zones(db: Session, owner_id: int, query: HostedZoneListQuery) -> HostedZoneListResponse:
    filters = [HostedZone.owner_id == owner_id]
    if query.zone_type is not None:
        filters.append(HostedZone.zone_type == query.zone_type)
    if query.search:
        filters.append(or_(*[
            column.icontains(query.search, autoescape=True)
            for column in (HostedZone.name, HostedZone.comment, HostedZone.id)
        ]))
    total = db.scalar(select(func.count()).select_from(HostedZone).where(*filters)) or 0
    column = SORT_COLUMNS[query.sort_by]
    order = column.asc() if query.sort_order == SortOrder.ASC else column.desc()
    # A stable tie-breaker prevents duplicate names/timestamps from shuffling pages.
    rows = db.execute(
        response_query().where(*filters).order_by(order, HostedZone.id.asc())
        .limit(query.page_size).offset((query.page - 1) * query.page_size)
    ).mappings().all()
    return HostedZoneListResponse(
        items=[HostedZoneResponse.model_validate(row) for row in rows],
        page=query.page, page_size=query.page_size, total=total,
        pages=(total + query.page_size - 1) // query.page_size,
    )


def get_hosted_zone(db: Session, owner_id: int, zone_id: str) -> HostedZoneResponse:
    row = db.execute(response_query().where(
        HostedZone.owner_id == owner_id, HostedZone.id == zone_id,
    )).mappings().one_or_none()
    if row is None:
        raise HostedZoneNotFound
    return HostedZoneResponse.model_validate(row)


def owned_zone(db: Session, owner_id: int, zone_id: str) -> HostedZone:
    zone = db.scalar(select(HostedZone).where(
        HostedZone.owner_id == owner_id, HostedZone.id == zone_id,
    ))
    if zone is None:
        raise HostedZoneNotFound
    return zone


def commit_change(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def create_hosted_zone(db: Session, owner_id: int, payload: HostedZoneCreate) -> HostedZoneResponse:
    for _ in range(ID_ATTEMPTS):
        candidate_id = generate_hosted_zone_id()
        # Avoid known collisions, but still handle the race at the database constraint.
        if db.scalar(select(HostedZone.id).where(HostedZone.id == candidate_id)) is not None:
            continue
        zone = HostedZone(id=candidate_id, owner_id=owner_id, **payload.model_dump())
        db.add(zone)
        try:
            add_default_system_records(zone)
            commit_change(db)
        except IntegrityError:
            db.rollback()
            if db.scalar(select(HostedZone.id).where(HostedZone.id == candidate_id)) is None:
                # An unrelated constraint failure must not be disguised as an ID collision.
                raise
            continue
        except Exception:
            # Also cover factory/flush hooks failing before commit_change runs.
            db.rollback()
            raise
        return get_hosted_zone(db, owner_id, candidate_id)
    raise HostedZoneIDUnavailable


def update_hosted_zone(
    db: Session, owner_id: int, zone_id: str, payload: HostedZoneUpdate,
) -> HostedZoneResponse:
    zone = owned_zone(db, owner_id, zone_id)
    changes = payload.model_dump(exclude_unset=True)
    merged = {field: getattr(zone, field) for field in EDITABLE_FIELDS}
    if zone.zone_type == ZoneType.PRIVATE and changes.get("zone_type") == ZoneType.PUBLIC:
        # Clear old private metadata; explicit conflicting input still fails validation.
        merged.update(vpc_id=None, region=None)
    merged.update(changes)
    try:
        validated = HostedZoneCreate.model_validate(merged)
    except ValidationError as exc:
        raise HostedZoneUpdateInvalid(exc) from exc
    # No ORM state is changed until the complete resulting zone is valid.
    previous_name = zone.name
    try:
        for field, value in validated.model_dump().items():
            setattr(zone, field, value)
        if zone.name != previous_name:
            synchronize_system_record_names(db, zone)
        zone.updated_at = utc_now()
        commit_change(db)
    except IntegrityError as exc:
        db.rollback()
        if "UNIQUE constraint failed: dns_records.hosted_zone_id, dns_records.name, dns_records.record_type" in str(exc.orig):
            raise HostedZoneRecordConflict from None
        raise
    except Exception:
        db.rollback()
        raise
    return get_hosted_zone(db, owner_id, zone_id)


def delete_hosted_zone(db: Session, owner_id: int, zone_id: str) -> None:
    zone = owned_zone(db, owner_id, zone_id)
    db.delete(zone)
    commit_change(db)
