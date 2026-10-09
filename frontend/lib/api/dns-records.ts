import { ApiError, apiRequest } from "@/lib/api/client";
import { hostedZonePath } from "@/lib/api/hosted-zones";
import type { DNSRecord, DNSRecordListParams, DNSRecordListResponse, DNSRecordWrite } from "@/types/dns-record";

function apiRecordsPath(zoneId: string): string {
  return `/api/hosted-zones/${encodeURIComponent(zoneId)}/records`;
}

export function createRecordPath(zoneId: string): string {
  return `${hostedZonePath(zoneId)}/records/create`;
}

export function editRecordPath(zoneId: string, recordId: string): string {
  return `${hostedZonePath(zoneId)}/records/${encodeURIComponent(recordId)}/edit`;
}

export async function listDNSRecords(zoneId: string, params: DNSRecordListParams, signal?: AbortSignal): Promise<DNSRecordListResponse> {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(name, String(value));
  }
  const result = await apiRequest<DNSRecordListResponse>(`${apiRecordsPath(zoneId)}${query.size ? `?${query}` : ""}`, {
    signal, cache: "no-store",
  });
  if (!result) throw new ApiError("The API returned an empty records response.", 200);
  return result;
}

export async function getDNSRecord(zoneId: string, recordId: string, signal?: AbortSignal): Promise<DNSRecord> {
  const record = await apiRequest<DNSRecord>(`${apiRecordsPath(zoneId)}/${encodeURIComponent(recordId)}`, { signal, cache: "no-store" });
  if (!record) throw new ApiError("The API returned an empty record response.", 200);
  return record;
}

export async function createDNSRecord(zoneId: string, payload: DNSRecordWrite): Promise<DNSRecord> {
  const record = await apiRequest<DNSRecord>(apiRecordsPath(zoneId), { method: "POST", json: { ...payload } });
  if (!record) throw new ApiError("The API returned an empty record response.", 201);
  return record;
}

export async function updateDNSRecord(zoneId: string, recordId: string, payload: DNSRecordWrite): Promise<DNSRecord> {
  const record = await apiRequest<DNSRecord>(`${apiRecordsPath(zoneId)}/${encodeURIComponent(recordId)}`, { method: "PATCH", json: { ...payload } });
  if (!record) throw new ApiError("The API returned an empty record response.", 200);
  return record;
}

export async function deleteDNSRecord(zoneId: string, recordId: string): Promise<void> {
  await apiRequest(`${apiRecordsPath(zoneId)}/${encodeURIComponent(recordId)}`, { method: "DELETE" });
}
