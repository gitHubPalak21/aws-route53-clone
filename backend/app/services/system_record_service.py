"""Mock Route 53 defaults; no AWS calls or real DNS delegation.

These helpers never commit. The hosted-zone service owns the transaction.
"""

import secrets

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import DNSRecord, HostedZone
from app.models.enums import DNSRecordType, RoutingPolicy

NS_TTL = 172800
SOA_TTL = 900
SOA_HOSTMASTER = "awsdns-hostmaster.amazon.com."
SOA_SERIAL = 1
SOA_REFRESH = 7200
SOA_RETRY = 900
SOA_EXPIRE = 1209600
SOA_MINIMUM = 86400
NAMESERVER_FAMILIES = ("com", "net", "org", "co.uk")
SYSTEM_RECORD_TYPES = (DNSRecordType.NS, DNSRecordType.SOA)


def generate_mock_nameservers() -> list[str]:
    """Four unique, trailing-dot names in distinct AWS-looking domain families."""
    return [
        f"ns-{family * 512 + secrets.randbelow(512) + 1}."
        f"awsdns-{secrets.randbelow(64):02d}.{suffix}."
        for family, suffix in enumerate(NAMESERVER_FAMILIES)
    ]


def add_default_system_records(zone: HostedZone) -> None:
    """Attach one pair to a new zone; repeated calls reuse a complete pair.

    This is a creation helper, not a historical-data backfill. Reject partial or
    duplicated pairs rather than silently inventing a replacement primary NS.
    """
    existing = [record for record in zone.records
                if record.is_system and record.record_type in SYSTEM_RECORD_TYPES]
    if existing:
        if len(existing) != 2 or {record.record_type for record in existing} != set(SYSTEM_RECORD_TYPES):
            raise ValueError("Hosted zone has an incomplete or duplicated system record pair")
        return

    nameservers = generate_mock_nameservers()
    soa = (
        f"{nameservers[0]} {SOA_HOSTMASTER} {SOA_SERIAL} {SOA_REFRESH} "
        f"{SOA_RETRY} {SOA_EXPIRE} {SOA_MINIMUM}"
    )
    zone.records.extend([
        DNSRecord(name=zone.name, record_type=DNSRecordType.NS, values=nameservers,
                  ttl=NS_TTL, routing_policy=RoutingPolicy.SIMPLE, alias=False, is_system=True),
        DNSRecord(name=zone.name, record_type=DNSRecordType.SOA, values=[soa],
                  ttl=SOA_TTL, routing_policy=RoutingPolicy.SIMPLE, alias=False, is_system=True),
    ])


def synchronize_system_record_names(db: Session, zone: HostedZone) -> None:
    """Rename only system NS/SOA owners, retaining IDs, values and TTLs."""
    db.execute(update(DNSRecord).where(
        DNSRecord.hosted_zone_id == zone.id,
        DNSRecord.is_system.is_(True),
        DNSRecord.record_type.in_(SYSTEM_RECORD_TYPES),
    ).values(name=zone.name))
