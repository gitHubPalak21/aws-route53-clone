from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.models.enums import ZoneType

if TYPE_CHECKING:
    from app.models.dns_record import DNSRecord
    from app.models.user import User


class HostedZone(TimestampMixin, Base):
    __tablename__ = "hosted_zones"
    __table_args__ = (
        CheckConstraint(
            "zone_type != 'PRIVATE' OR "
            "(vpc_id IS NOT NULL AND length(trim(vpc_id)) > 0 "
            "AND region IS NOT NULL AND length(trim(region)) > 0)",
            name="private_zone_vpc",
        ),
    )

    # The zone service supplies an AWS-style public ID, e.g. Z0123456789ABCDEF.
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(253), index=True)
    comment: Mapped[str | None] = mapped_column(Text)
    zone_type: Mapped[ZoneType] = mapped_column(
        Enum(
            ZoneType, native_enum=False, create_constraint=True,
            validate_strings=True, name="zone_type",
        ),
        default=ZoneType.PUBLIC,
        server_default=ZoneType.PUBLIC.value,
    )
    vpc_id: Mapped[str | None] = mapped_column(String(32))
    region: Mapped[str | None] = mapped_column(String(64))

    owner: Mapped[User] = relationship(back_populates="hosted_zones")
    records: Mapped[list[DNSRecord]] = relationship(
        back_populates="hosted_zone", cascade="all, delete-orphan", passive_deletes=True
    )
