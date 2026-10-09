export type HostedZoneType = "PUBLIC" | "PRIVATE";
export type HostedZoneSortField = "name" | "zone_type" | "created_at" | "updated_at" | "id";
export type SortOrder = "asc" | "desc";

export interface HostedZone {
  id: string;
  name: string;
  comment: string | null;
  zone_type: HostedZoneType;
  vpc_id: string | null;
  region: string | null;
  record_count: number;
  created_at: string;
  updated_at: string;
}

export interface HostedZoneListResponse {
  items: HostedZone[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface HostedZoneListParams {
  search?: string;
  page?: number;
  page_size?: number;
  sort_by?: HostedZoneSortField;
  sort_order?: SortOrder;
  zone_type?: HostedZoneType;
}

export interface HostedZoneWrite {
  name: string;
  comment: string | null;
  zone_type: HostedZoneType;
  vpc_id: string | null;
  region: string | null;
}

export const HOSTED_ZONE_TYPE_LABELS: Record<HostedZoneType, string> = {
  PUBLIC: "Public",
  PRIVATE: "Private",
};
