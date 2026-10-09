import { ApiError, apiRequest } from "@/lib/api/client";
import type { HostedZone, HostedZoneListParams, HostedZoneListResponse, HostedZoneWrite } from "@/types/hosted-zone";

/** Server-side collection operations share the application's credentialed client. */
export async function listHostedZones(
  params: HostedZoneListParams,
  signal?: AbortSignal,
): Promise<HostedZoneListResponse> {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(name, String(value));
  }
  const suffix = query.size ? `?${query.toString()}` : "";
  const result = await apiRequest<HostedZoneListResponse>(`/api/hosted-zones${suffix}`, {
    signal,
    cache: "no-store",
  });
  if (!result) throw new ApiError("The API returned an empty hosted zones response.", 200);
  return result;
}

export function hostedZonePath(id: string): string {
  return `/route53/hosted-zones/${encodeURIComponent(id)}`;
}

function apiZonePath(id: string): string {
  return `/api/hosted-zones/${encodeURIComponent(id)}`;
}

function requireZone(zone: HostedZone | undefined): HostedZone {
  if (!zone) throw new ApiError("The API returned an empty hosted zone response.", 200);
  return zone;
}

export async function getHostedZone(id: string, signal?: AbortSignal): Promise<HostedZone> {
  return requireZone(await apiRequest<HostedZone>(apiZonePath(id), { signal, cache: "no-store" }));
}

export async function createHostedZone(payload: HostedZoneWrite): Promise<HostedZone> {
  return requireZone(await apiRequest<HostedZone>("/api/hosted-zones", { method: "POST", json: { ...payload } }));
}

export async function updateHostedZone(id: string, payload: Partial<HostedZoneWrite>): Promise<HostedZone> {
  return requireZone(await apiRequest<HostedZone>(apiZonePath(id), { method: "PATCH", json: { ...payload } }));
}

export async function deleteHostedZone(id: string): Promise<void> {
  await apiRequest(apiZonePath(id), { method: "DELETE" });
}
