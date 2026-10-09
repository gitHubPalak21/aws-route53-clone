from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Enum, ForeignKey, Index, Integer, String, false, text,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import DNSRecordType, RoutingPolicy

if TYPE_CHECKING:
    from app.models.hosted_zone import HostedZone


class DNSRecord(TimestampMixin, Base):
    __tablename__ = "dns_records"
    __table_args__ = (
        Index("uq_dns_records_zone_name_type", "hosted_zone_id", "name", "record_type", unique=True),
        CheckConstraint("ttl IS NULL OR ttl > 0", name="positive_ttl"),
        CheckConstraint('json_type("values") = \'array\'', name="values_array"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    hosted_zone_id: Mapped[str] = mapped_column(
        ForeignKey("hosted_zones.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(253), index=True)
    record_type: Mapped[DNSRecordType] = mapped_column(
        Enum(
            DNSRecordType, native_enum=False, create_constraint=True,
            validate_strings=True, name="record_type",
        ),
        index=True,
    )
    values: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON()), default=list, server_default=text("'[]'")
    )
    # evaluates_none preserves an explicitly supplied NULL for future alias records.
    ttl: Mapped[int | None] = mapped_column(
        Integer().evaluates_none(), default=300, server_default=text("300")
    )
    routing_policy: Mapped[RoutingPolicy] = mapped_column(
        Enum(
            RoutingPolicy, native_enum=False, create_constraint=True,
            validate_strings=True, name="routing_policy",
        ),
        default=RoutingPolicy.SIMPLE,
        server_default=RoutingPolicy.SIMPLE.value,
    )
    alias: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="alias_boolean"),
        default=False,
        server_default=false(),
    )
    alias_target: Mapped[dict[str, object] | None] = mapped_column(
        MutableDict.as_mutable(JSON(none_as_null=True))
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="is_system_boolean"),
        default=False,
        server_default=false(),
    )

    hosted_zone: Mapped[HostedZone] = relationship(back_populates="records")
