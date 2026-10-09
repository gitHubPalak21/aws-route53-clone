import type { SortOrder } from "@/types/hosted-zone";
import type { JsonValue } from "@/types/api";

export const USER_RECORD_TYPES = ["A", "AAAA", "CNAME", "TXT", "MX", "NS", "PTR", "SRV", "CAA"] as const;
export const DNS_RECORD_TYPES = [...USER_RECORD_TYPES, "SOA"] as const;
export type DNSRecordType = typeof DNS_RECORD_TYPES[number];
export type UserDNSRecordType = Exclude<DNSRecordType, "SOA">;
export interface DNSRecordWrite {
  name: string;
  record_type: UserDNSRecordType;
  values: string[];
  ttl: number;
  routing_policy: "SIMPLE";
}
export type DNSRecordSortField = "name" | "record_type" | "ttl" | "created_at" | "updated_at";

export interface DNSRecord {
  id: string;
  hosted_zone_id: string;
  name: string;
  record_type: DNSRecordType;
  values: string[];
  ttl: number | null;
  routing_policy: "SIMPLE";
  alias: boolean;
  alias_target: { [key: string]: JsonValue } | null;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface DNSRecordListResponse {
  items: DNSRecord[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface DNSRecordListParams {
  search?: string;
  record_type?: DNSRecordType;
  page?: number;
  page_size?: number;
  sort_by?: DNSRecordSortField;
  sort_order?: SortOrder;
}

export const ROUTING_POLICY_LABELS = { SIMPLE: "Simple" } as const;
export function formatRecordTTL(ttl: number | null): string {
  return ttl === null ? "—" : String(ttl);
}
