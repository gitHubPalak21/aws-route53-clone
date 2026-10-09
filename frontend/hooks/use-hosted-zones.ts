"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { listHostedZones } from "@/lib/api/hosted-zones";
import type { HostedZoneListParams, HostedZoneListResponse } from "@/types/hosted-zone";

interface Result {
  key: string;
  data: HostedZoneListResponse | null;
  error: string | null;
}

export function useHostedZones(params: HostedZoneListParams) {
  const { refreshUser } = useAuth();
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const { search, page, page_size, sort_by, sort_order, zone_type } = params;
  const query = useMemo<HostedZoneListParams>(() => ({ search, page, page_size, sort_by, sort_order, zone_type }),
    [search, page, page_size, sort_by, sort_order, zone_type]);
  const queryKey = JSON.stringify(query);
  const requestKey = `${queryKey}:${revision}`;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    listHostedZones(query, controller.signal).then(
      (data) => {
        if (active) setResult({ key: requestKey, data, error: null });
      },
      (error: unknown) => {
        if (!active || controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 401) {
          // The shared auth provider/guard owns session revalidation and login redirects.
          void refreshUser();
          return;
        }
        setResult({ key: requestKey, data: null, error: "Hosted zones could not be loaded. Try again." });
      },
    );
    return () => {
      active = false;
      controller.abort();
    };
  }, [query, requestKey, refreshUser]);

  const refetch = useCallback(() => setRevision((value) => value + 1), []);
  // A response for an older query is never displayed while the next query loads.
  const current = result?.key === requestKey ? result : null;
  return { data: current?.data ?? null, error: current?.error ?? null, isLoading: !current, refetch };
}
