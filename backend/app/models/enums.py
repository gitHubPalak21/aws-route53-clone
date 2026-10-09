from enum import StrEnum


class ZoneType(StrEnum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"


class DNSRecordType(StrEnum):
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    TXT = "TXT"
    MX = "MX"
    NS = "NS"
    PTR = "PTR"
    SRV = "SRV"
    CAA = "CAA"
    SOA = "SOA"


class RoutingPolicy(StrEnum):
    SIMPLE = "SIMPLE"
