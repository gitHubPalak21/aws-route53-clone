"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { getDNSRecord, listDNSRecords } from "@/lib/api/dns-records";
import type { DNSRecord, DNSRecordListParams, DNSRecordListResponse } from "@/types/dns-record";

type RecordError = "missing" | "failed" | null;

export function useDNSRecords(zoneId: string, params: DNSRecordListParams) {
  const { refreshUser } = useAuth();
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ key: string; data: DNSRecordListResponse | null; error: RecordError } | null>(null);
  const { search, record_type, page, page_size, sort_by, sort_order } = params;
  const query = useMemo<DNSRecordListParams>(() => ({ search, record_type, page, page_size, sort_by, sort_order }),
    [search, record_type, page, page_size, sort_by, sort_order]);
  const queryKey = JSON.stringify(query);
  const key = `${zoneId}:${queryKey}:${revision}`;
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    listDNSRecords(zoneId, query, controller.signal).then((data) => {
      if (active) setResult({ key, data, error: null });
    }, (error: unknown) => {
      if (!active || controller.signal.aborted) return;
      if (error instanceof ApiError && error.status === 401) { void refreshUser(); return; }
      setResult({ key, data: null, error: error instanceof ApiError && error.status === 404 ? "missing" : "failed" });
    });
    return () => { active = false; controller.abort(); };
  }, [zoneId, query, key, refreshUser]);
  const refetch = useCallback(() => setRevision((value) => value + 1), []);
  const current = result?.key === key ? result : null;
  return { data: current?.data ?? null, error: current?.error ?? null, isLoading: !current, refetch };
}

/** Fetches the actual record independently for direct edit navigation and refresh. */
export function useDNSRecord(zoneId: string, recordId?: string) {
  const { refreshUser } = useAuth();
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{ key: string; record: DNSRecord | null; error: RecordError } | null>(null);
  const key = `${zoneId}:${recordId}:${revision}`;
  useEffect(() => {
    if (!recordId) return;
    let active = true;
    const controller = new AbortController();
    getDNSRecord(zoneId, recordId, controller.signal).then((record) => {
      if (active) setResult({ key, record, error: null });
    }, (error: unknown) => {
      if (!active || controller.signal.aborted) return;
      if (error instanceof ApiError && error.status === 401) { void refreshUser(); return; }
      setResult({ key, record: null, error: error instanceof ApiError && error.status === 404 ? "missing" : "failed" });
    });
    return () => { active = false; controller.abort(); };
  }, [zoneId, recordId, key, refreshUser]);
  const current = result?.key === key ? result : null;
  const refetch = useCallback(() => setRevision((value) => value + 1), []);
  return { record: current?.record ?? null, error: current?.error ?? null, isLoading: Boolean(recordId) && !current, refetch };
}
