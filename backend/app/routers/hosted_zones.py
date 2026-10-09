from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.exceptions import RequestValidationError

from app.dependencies.auth import CurrentUser, Database, require_trusted_origin
from app.schemas.auth import AuthErrorResponse
from app.schemas.hosted_zone import (
    HostedZoneCreate, HostedZoneListQuery, HostedZoneListResponse,
    HostedZoneResponse, HostedZoneUpdate,
)
from app.services import hosted_zone_service as service


def disable_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/hosted-zones", tags=["Hosted Zones"],
    dependencies=[Depends(disable_cache)],
    responses={401: {"model": AuthErrorResponse, "description": "Session authentication required"}},
)
ZoneID = Annotated[str, Path(pattern=r"^Z[A-Z0-9]{1,31}$", description="Hosted zone ID, starting with Z")]
not_found = {404: {"model": AuthErrorResponse, "description": "Zone missing or owned by another user"}}
write_errors = {403: {"model": AuthErrorResponse, "description": "Untrusted browser Origin"}}


def missing_zone() -> HTTPException:
    return HTTPException(404, "Hosted zone not found", headers={"Cache-Control": "no-store"})


@router.get("", response_model=HostedZoneListResponse, summary="List, search and paginate your hosted zones")
def list_zones(
    query: Annotated[HostedZoneListQuery, Query()], user: CurrentUser, db: Database,
) -> HostedZoneListResponse:
    return service.list_hosted_zones(db, user.id, query)


@router.post("", response_model=HostedZoneResponse, status_code=201,
             responses={**write_errors, 503: {"model": AuthErrorResponse, "description": "ID allocation unavailable"}},
             dependencies=[Depends(require_trusted_origin)], summary="Create a hosted zone with mocked NS and SOA records",
             description="Atomically creates the zone and two system records for PUBLIC and PRIVATE zones. "
                         "Name servers are mock AWS-style values; no real DNS delegation occurs.")
def create_zone(payload: HostedZoneCreate, user: CurrentUser, db: Database) -> HostedZoneResponse:
    try:
        return service.create_hosted_zone(db, user.id, payload)
    except service.HostedZoneIDUnavailable:
        raise HTTPException(503, "Unable to allocate a hosted zone ID; retry the request",
                            headers={"Cache-Control": "no-store", "Retry-After": "1"}) from None


@router.get("/{zone_id}", response_model=HostedZoneResponse, responses=not_found, summary="Get your hosted zone")
def get_zone(zone_id: ZoneID, user: CurrentUser, db: Database) -> HostedZoneResponse:
    try:
        return service.get_hosted_zone(db, user.id, zone_id)
    except service.HostedZoneNotFound:
        raise missing_zone() from None


@router.patch("/{zone_id}", response_model=HostedZoneResponse, responses={**not_found, **write_errors,
              409: {"model": AuthErrorResponse, "description": "Rename conflicts with an existing NS/SOA record set"}},
              dependencies=[Depends(require_trusted_origin)], summary="Update and validate the resulting hosted zone")
def update_zone(zone_id: ZoneID, payload: HostedZoneUpdate, user: CurrentUser, db: Database) -> HostedZoneResponse:
    try:
        return service.update_hosted_zone(db, user.id, zone_id, payload)
    except service.HostedZoneNotFound:
        raise missing_zone() from None
    except service.HostedZoneRecordConflict:
        raise HTTPException(409, "Hosted zone rename conflicts with an existing NS/SOA record set",
                            headers={"Cache-Control": "no-store"}) from None
    except service.HostedZoneUpdateInvalid as exc:
        # Reuse the application's sanitized validation error response for merged state.
        errors = [{**error, "loc": ("body", *error["loc"])} for error in exc.errors]
        raise RequestValidationError(errors) from None


@router.delete("/{zone_id}", status_code=204, responses={**not_found, **write_errors},
               dependencies=[Depends(require_trusted_origin)], summary="Delete your zone and cascade its DNS records")
def delete_zone(zone_id: ZoneID, user: CurrentUser, db: Database) -> Response:
    try:
        service.delete_hosted_zone(db, user.id, zone_id)
    except service.HostedZoneNotFound:
        raise missing_zone() from None
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
