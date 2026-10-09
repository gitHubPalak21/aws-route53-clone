from datetime import datetime
from enum import StrEnum
import re
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.models.enums import ZoneType


def trim_string(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def normalize_domain(value: str) -> str:
    name = value.strip().lower().removesuffix(".")
    labels = name.split(".")
    if len(name) > 253 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in labels
    ):
        raise ValueError("Use an ASCII DNS name with labels of 1–63 characters and a total length of at most 253")
    return name


DomainName = Annotated[str, AfterValidator(normalize_domain)]
VPCId = Annotated[str, BeforeValidator(trim_string), Field(pattern=r"^vpc-[0-9a-f]{8,17}$")]
Comment = Annotated[str, Field(max_length=1024)]


class SupportedRegion(StrEnum):
    US_EAST_1 = "us-east-1"
    US_EAST_2 = "us-east-2"
    US_WEST_1 = "us-west-1"
    US_WEST_2 = "us-west-2"
    EU_WEST_1 = "eu-west-1"
    EU_CENTRAL_1 = "eu-central-1"
    AP_SOUTH_1 = "ap-south-1"
    AP_SOUTHEAST_1 = "ap-southeast-1"
    AP_SOUTHEAST_2 = "ap-southeast-2"
    AP_NORTHEAST_1 = "ap-northeast-1"


Region = Annotated[SupportedRegion, BeforeValidator(trim_string)]


class HostedZoneCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"name": "example.com", "comment": "Production website", "zone_type": "PUBLIC"},
        {"name": "internal.example.com", "zone_type": "PRIVATE",
         "vpc_id": "vpc-0123456789abcdef", "region": "ap-south-1"},
    ]})

    name: DomainName = Field(description="ASCII DNS name, stored lowercase without a trailing dot")
    comment: Comment | None = None
    zone_type: ZoneType = ZoneType.PUBLIC
    vpc_id: VPCId | None = None
    region: Region | None = None

    @model_validator(mode="after")
    def validate_metadata(self) -> Self:
        if self.zone_type == ZoneType.PRIVATE and (self.vpc_id is None or self.region is None):
            raise ValueError("PRIVATE hosted zones require vpc_id and region")
        if self.zone_type == ZoneType.PUBLIC and (self.vpc_id is not None or self.region is not None):
            raise ValueError("PUBLIC hosted zones cannot specify VPC fields")
        return self


class HostedZoneUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"comment": "Updated description"}, {"zone_type": "PUBLIC"},
    ]})

    name: DomainName | None = None
    comment: Comment | None = None
    zone_type: ZoneType | None = None
    vpc_id: VPCId | None = None
    region: Region | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply at least one editable field")
        for field in ("name", "zone_type"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class HostedZoneResponse(BaseModel):
    id: str
    name: str
    comment: str | None
    zone_type: ZoneType
    vpc_id: str | None
    region: SupportedRegion | None
    record_count: int = Field(ge=0, description="Derived count of stored DNS records; never persisted on the zone")
    created_at: datetime
    updated_at: datetime


class HostedZoneListResponse(BaseModel):
    items: list[HostedZoneResponse]
    page: int
    page_size: int
    total: int
    pages: int


class HostedZoneSortField(StrEnum):
    NAME = "name"
    ZONE_TYPE = "zone_type"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    ID = "id"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class HostedZoneListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, le=2_147_483_647, description="One-based page number")
    page_size: int = Field(default=20, ge=1, le=100)
    search: Annotated[str, BeforeValidator(trim_string)] | None = Field(
        default=None, max_length=253, description="Literal substring in name, comment or ID; ASCII case-insensitive"
    )
    sort_by: HostedZoneSortField = HostedZoneSortField.NAME
    sort_order: SortOrder = SortOrder.ASC
    zone_type: ZoneType | None = Field(default=None, description="Optional PUBLIC/PRIVATE filter")
