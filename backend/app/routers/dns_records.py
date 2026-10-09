from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.exceptions import RequestValidationError

from app.dependencies.auth import CurrentUser, Database, require_trusted_origin
from app.routers.hosted_zones import ZoneID, disable_cache
from app.schemas.auth import AuthErrorResponse
from app.schemas.dns_record import (
    DNSRecordCreate, DNSRecordListQuery, DNSRecordListResponse, DNSRecordResponse, DNSRecordUpdate,
)
from app.services import dns_record_service as service
from app.services.hosted_zone_service import HostedZoneNotFound

router = APIRouter(
    prefix="/api/hosted-zones/{zone_id}/records", tags=["DNS Records"],
    dependencies=[Depends(disable_cache)],
    responses={401: {"model": AuthErrorResponse, "description": "Session authentication required"},
               404: {"model": AuthErrorResponse, "description": "Zone/record missing, cross-zone or owned by another user"}},
)
RecordID = Annotated[str, Path(min_length=1, max_length=36, description="DNS record UUID")]
write_responses = {
    403: {"model": AuthErrorResponse, "description": "Untrusted browser Origin"},
    409: {"model": AuthErrorResponse, "description": "Duplicate record set or protected system record"},
}


def api_error(exc: Exception) -> Exception:
    if isinstance(exc, (HostedZoneNotFound, service.DNSRecordNotFound)):
        return HTTPException(404, "DNS record or hosted zone not found", headers={"Cache-Control": "no-store"})
    if isinstance(exc, service.DNSRecordConflict):
        return HTTPException(409, str(exc), headers={"Cache-Control": "no-store"})
    if isinstance(exc, service.DNSRecordInvalid):
        return RequestValidationError([{**error, "loc": ("body", *error["loc"])} for error in exc.errors])
    return exc


ERRORS = (HostedZoneNotFound, service.DNSRecordNotFound, service.DNSRecordConflict, service.DNSRecordInvalid)


@router.get("", response_model=DNSRecordListResponse, summary="List, search, filter and paginate DNS records",
            description="Includes read-only system NS/SOA. Search is a literal substring of name or serialized JSON values; "
                        "filter by record_type/system, sort through a whitelist, and paginate in SQL with page/page_size.")
def list_records(zone_id: ZoneID, query: Annotated[DNSRecordListQuery, Query()], user: CurrentUser, db: Database) -> DNSRecordListResponse:
    try:
        return service.list_records(db, user.id, zone_id, query)
    except ERRORS as exc:
        raise api_error(exc) from None


@router.post("", response_model=DNSRecordResponse, status_code=201, responses=write_responses,
             dependencies=[Depends(require_trusted_origin)], summary="Create an ordinary DNS record set",
             description="Supports A, AAAA, CNAME, TXT, MX, NS, PTR, SRV and CAA. Values are normalized and deduplicated. "
                         "SOA, aliases and advanced routing are unavailable. One SIMPLE record set per zone/name/type; "
                         "records are stored locally, without actual DNS resolution.")
def create_record(zone_id: ZoneID, payload: DNSRecordCreate, user: CurrentUser, db: Database) -> DNSRecordResponse:
    try:
        return service.create_record(db, user.id, zone_id, payload)
    except ERRORS as exc:
        raise api_error(exc) from None


@router.get("/{record_id}", response_model=DNSRecordResponse, summary="Get an ordinary or system DNS record")
def get_record(zone_id: ZoneID, record_id: RecordID, user: CurrentUser, db: Database) -> DNSRecordResponse:
    try:
        return service.get_record(db, user.id, zone_id, record_id)
    except ERRORS as exc:
        raise api_error(exc) from None


@router.patch("/{record_id}", response_model=DNSRecordResponse, responses=write_responses,
              dependencies=[Depends(require_trusted_origin)], summary="Update and validate a DNS record set",
              description="Editable name/type/values/ttl/routing_policy. Validates the complete resulting state, "
                          "including changed types and uniqueness. System-managed records are read-only.")
def update_record(zone_id: ZoneID, record_id: RecordID, payload: DNSRecordUpdate, user: CurrentUser, db: Database) -> DNSRecordResponse:
    try:
        return service.update_record(db, user.id, zone_id, record_id, payload)
    except ERRORS as exc:
        raise api_error(exc) from None


@router.delete("/{record_id}", status_code=204, responses=write_responses,
               dependencies=[Depends(require_trusted_origin)], summary="Delete an ordinary DNS record",
               description="System records cannot be deleted individually. Hosted-zone deletion still cascades all records.")
def delete_record(zone_id: ZoneID, record_id: RecordID, user: CurrentUser, db: Database) -> Response:
    try:
        service.delete_record(db, user.id, zone_id, record_id)
    except ERRORS as exc:
        raise api_error(exc) from None
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
