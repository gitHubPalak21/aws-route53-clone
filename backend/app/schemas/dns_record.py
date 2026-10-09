from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, StrictBool, StrictInt, ValidationInfo, field_validator, model_validator

from app.models.enums import DNSRecordType, RoutingPolicy
from app.schemas.hosted_zone import SortOrder, trim_string
from app.services.dns_validation import normalize_record_values


class DNSRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    hosted_zone_id: str
    name: str
    record_type: DNSRecordType
    values: list[str]
    ttl: int | None
    routing_policy: RoutingPolicy
    alias: bool
    alias_target: dict[str, JsonValue] | None
    is_system: bool
    created_at: datetime
    updated_at: datetime


RecordName = Annotated[str, BeforeValidator(trim_string), Field(max_length=253)]
RecordValues = Annotated[list[Annotated[str, Field(max_length=4096)]], Field(min_length=1, max_length=100)]
RecordTTL = Annotated[StrictInt, Field(gt=0, le=2_147_483_647)]


class DNSRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"name": "www", "record_type": "A", "values": ["192.0.2.10"], "ttl": 300},
        {"name": "_sip._tcp", "record_type": "SRV", "values": ["10 5 443 service.example.com"]},
    ]})

    name: RecordName = Field(description="Single relative label, in-zone FQDN, or @/empty for apex; SRV also accepts _service._protocol")
    record_type: DNSRecordType = Field(description="A, AAAA, CNAME, TXT, MX, NS, PTR, SRV or CAA; SOA is system-managed")
    values: RecordValues = Field(description="1–100 nonblank values, each at most 4096 characters; normalized and deduplicated in order")
    ttl: RecordTTL = 300
    routing_policy: RoutingPolicy = RoutingPolicy.SIMPLE
    alias: StrictBool = Field(default=False, description="Only false is supported")
    alias_target: None = None

    @field_validator("alias")
    @classmethod
    def no_alias(cls, value: bool) -> bool:
        if value:
            raise ValueError("Alias records are not supported in this clone yet")
        return value

    @field_validator("record_type")
    @classmethod
    def no_soa(cls, value: DNSRecordType) -> DNSRecordType:
        if value == DNSRecordType.SOA:
            raise ValueError("SOA records are system-managed and cannot be created or selected")
        return value

    @field_validator("values")
    @classmethod
    def valid_values(cls, values: list[str], info: ValidationInfo) -> list[str]:
        record_type = info.data.get("record_type")
        return normalize_record_values(record_type, values) if record_type else values


class DNSRecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"values": ["192.0.2.20"], "ttl": 600},
    ]})

    name: RecordName | None = None
    record_type: DNSRecordType | None = None
    values: RecordValues | None = None
    ttl: RecordTTL | None = None
    routing_policy: RoutingPolicy | None = None

    @model_validator(mode="after")
    def valid_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Supply at least one editable field")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class DNSRecordResponse(DNSRecordRead):
    """Public contract also serializes existing system records and future nullable TTLs."""


class DNSRecordSortField(StrEnum):
    NAME = "name"
    RECORD_TYPE = "record_type"
    TTL = "ttl"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class DNSRecordListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, le=2_147_483_647)
    page_size: int = Field(default=20, ge=1, le=100)
    search: Annotated[str, BeforeValidator(trim_string)] | None = Field(
        default=None, max_length=4096, description="Literal substring of name or serialized JSON values; ASCII case-insensitive"
    )
    record_type: DNSRecordType | None = None
    system: bool | None = Field(default=None, description="Optional system/user record filter")
    sort_by: DNSRecordSortField = DNSRecordSortField.NAME
    sort_order: SortOrder = SortOrder.ASC


class DNSRecordListResponse(BaseModel):
    items: list[DNSRecordResponse]
    page: int
    page_size: int
    total: int
    pages: int
