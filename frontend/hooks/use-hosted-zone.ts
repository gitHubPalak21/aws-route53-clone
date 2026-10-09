"use client";

import { useCallback, useEffect, useState } from "react";
import { useHostedZoneContext } from "@/components/hosted-zones/hosted-zone-context";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { getHostedZone } from "@/lib/api/hosted-zones";
import type { HostedZone } from "@/types/hosted-zone";

export function useHostedZone(id: string, retainOnRefresh = false) {
  const { refreshUser } = useAuth();
  const { setResource } = useHostedZoneContext();
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ key: string; zone: HostedZone | null; error: "missing" | "failed" | null } | null>(null);
  const key = `${id}:${revision}`;
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    getHostedZone(id, controller.signal).then((zone) => {
      if (active) {
        setResult({ key, zone, error: null });
        setResource({ id: zone.id, name: zone.name });
      }
    }, (error: unknown) => {
      if (!active || controller.signal.aborted) return;
      if (error instanceof ApiError && error.status === 401) { void refreshUser(); return; }
      setResult({ key, zone: null, error: error instanceof ApiError && error.status === 404 ? "missing" : "failed" });
    });
    return () => { active = false; controller.abort(); };
  }, [id, key, refreshUser, setResource]);
  const refetch = useCallback(() => setRevision((value) => value + 1), []);
  const current = result?.key === key ? result : null;
  const retained = retainOnRefresh && result?.zone?.id === id ? result.zone : null;
  return { zone: current ? current.zone : retained, error: current?.error ?? null, loading: !current, refetch };
}
