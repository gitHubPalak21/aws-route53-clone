"""Practical DNS storage validation, without DNS lookups or AWS requests."""

from ipaddress import IPv4Address, IPv6Address, ip_address
import re

from app.models.enums import DNSRecordType

HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
SERVICE_LABEL = re.compile(r"_[a-z0-9](?:[a-z0-9-]{0,60}[a-z0-9])?")
UNDERSCORE_TYPES = {DNSRecordType.SRV, DNSRecordType.TXT}


def valid_labels(name: str, *, service: bool = False, wildcard: bool = False) -> bool:
    labels = name.split(".")
    return bool(name) and len(name) <= 253 and all(
        HOST_LABEL.fullmatch(label)
        or (service and SERVICE_LABEL.fullmatch(label))
        or (wildcard and index == 0 and label == "*")
        for index, label in enumerate(labels)
    )


def normalize_hostname(value: str) -> str:
    """Store hostname targets lowercase with one trailing dot; reject IPs/URLs."""
    name = value.strip().lower().removesuffix(".")
    if not valid_labels(name) or all(label.isdigit() for label in name.split(".")):
        raise ValueError("Use a valid ASCII hostname, without a protocol or IP address")
    try:
        ip_address(name)
    except ValueError:
        return name + "."
    raise ValueError("Use a hostname rather than an IP address")


def normalize_record_name(value: str, zone_name: str, record_type: DNSRecordType) -> str:
    """Single labels are relative; dotted inputs must be in-zone FQDNs.

    Relative SRV service prefixes such as _sip._tcp are also accepted.
    An explicit trailing dot always denotes an absolute name.
    """
    raw = value.strip().lower()
    absolute = raw.endswith(".")
    name = raw.removesuffix(".")
    if raw in {"", "@"}:
        name = zone_name
    elif name == zone_name or name.endswith("." + zone_name):
        pass
    elif not absolute and ("." not in name or (
        record_type == DNSRecordType.SRV and len(name.split(".")) == 2
        and all(SERVICE_LABEL.fullmatch(label) for label in name.split("."))
    )):
        name = f"{name}.{zone_name}"
    else:
        raise ValueError(f"Record name must belong to hosted zone {zone_name}")
    if not valid_labels(name, service=record_type in UNDERSCORE_TYPES,
                        wildcard=record_type != DNSRecordType.SRV):
        raise ValueError("Use an ASCII DNS record name with labels of 1–63 characters and at most 253 characters")
    if record_type == DNSRecordType.CNAME and name == zone_name:
        raise ValueError("CNAME records cannot be created at the hosted zone apex")
    return name


def unsigned_number(value: str, maximum: int, label: str) -> str:
    if not re.fullmatch(r"[0-9]+", value) or len(value) > 10 or int(value) > maximum:
        raise ValueError(f"{label} must be an integer between 0 and {maximum}")
    return str(int(value))


def normalize_record_values(record_type: DNSRecordType, values: list[str]) -> list[str]:
    if record_type == DNSRecordType.SOA:
        raise ValueError("SOA records are system-managed and cannot be created or selected")
    normalized = []
    for raw in values:
        value = raw.strip()
        if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Record values must be nonblank strings without control characters")
        if record_type in {DNSRecordType.A, DNSRecordType.AAAA}:
            address_class = IPv4Address if record_type == DNSRecordType.A else IPv6Address
            try:
                # IPv6 scope IDs are not valid DNS AAAA address data.
                if "%" in value:
                    raise ValueError
                value = str(address_class(value))
            except ValueError:
                version = "IPv4" if record_type == DNSRecordType.A else "IPv6"
                raise ValueError(f"{record_type.value} record values must contain valid {version} addresses") from None
        elif record_type in {DNSRecordType.CNAME, DNSRecordType.NS, DNSRecordType.PTR}:
            value = normalize_hostname(value)
        elif record_type == DNSRecordType.TXT:
            # Accept simple surrounding quotes; do not interpret zone-file escapes/chunks.
            if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            if not value.strip():
                raise ValueError("TXT record values cannot be blank")
        elif record_type == DNSRecordType.MX:
            parts = value.split()
            if len(parts) != 2:
                raise ValueError("MX record values must use '<priority> <hostname>' format")
            value = f"{unsigned_number(parts[0], 65535, 'MX priority')} {normalize_hostname(parts[1])}"
        elif record_type == DNSRecordType.SRV:
            parts = value.split()
            if len(parts) != 4:
                raise ValueError("SRV record values must use '<priority> <weight> <port> <target>' format")
            numbers = [unsigned_number(part, 65535, f"SRV {label}")
                       for part, label in zip(parts[:3], ("priority", "weight", "port"))]
            target = "." if parts[3] == "." else normalize_hostname(parts[3])
            value = " ".join([*numbers, target])
        elif record_type == DNSRecordType.CAA:
            parts = value.split(maxsplit=2)
            if len(parts) != 3 or not re.fullmatch(r"[a-zA-Z0-9]{1,15}", parts[1]):
                raise ValueError("CAA record values must use '<flags> <tag> <value>' format with an alphanumeric tag")
            flags = unsigned_number(parts[0], 255, "CAA flags")
            content = parts[2]
            if len(content) >= 2 and content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
            if not content.strip():
                raise ValueError("CAA property value cannot be blank")
            value = f"{flags} {parts[1].lower()} {content}"
        if value not in normalized:
            normalized.append(value)
    if record_type == DNSRecordType.CNAME and len(normalized) != 1:
        raise ValueError("CNAME records require exactly one target value")
    return normalized
