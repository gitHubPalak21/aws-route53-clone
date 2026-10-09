"use client";

import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useEffect, useRef, useState } from "react";
import { useNotifications } from "@/components/notifications/notification-provider";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { deleteDNSRecord } from "@/lib/api/dns-records";
import { recordErrorFeedback } from "@/lib/api/dns-record-errors";
import type { DNSRecord } from "@/types/dns-record";
import { RecordValuesCell } from "./record-values-cell";

export function DeleteDNSRecordModal({ record, onDismiss, onDeleted }: {
  record: DNSRecord; onDismiss: () => void; onDeleted: () => void;
}) {
  const { success } = useNotifications();
  const { refreshUser } = useAuth();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function confirm() {
    if (pending.current || record.is_system) return;
    pending.current = true; setDeleting(true); setError(null);
    let deleted = false;
    try {
      await deleteDNSRecord(record.hosted_zone_id, record.id);
      deleted = true;
      if (mounted.current) { success(`Record ${record.name} deleted.`); onDeleted(); }
    } catch (failure: unknown) {
      if (!mounted.current) return;
      if (failure instanceof ApiError && failure.status === 401) { void refreshUser(); return; }
      setError(recordErrorFeedback(failure).message.replace("Your entries have been kept. ", ""));
    } finally {
      if (!deleted) { pending.current = false; if (mounted.current) setDeleting(false); }
    }
  }
  return <Modal visible header="Delete record?" closeAriaLabel="Close delete record confirmation"
    onDismiss={() => { if (!pending.current) onDismiss(); }}
    footer={<Box float="right"><SpaceBetween direction="horizontal" size="xs">
      <Button variant="link" formAction="none" disabled={deleting} onClick={onDismiss}>Cancel</Button>
      <Button variant="primary" disabled={record.is_system} loading={deleting} loadingText="Deleting record" onClick={() => void confirm()}>Delete</Button>
    </SpaceBetween></Box>}>
    <SpaceBetween size="m">
      {error && <div role="alert"><Alert type="error" header="Unable to delete record">{error}</Alert></div>}
      {record.is_system ? <Alert type="info">System-managed DNS records cannot be deleted.</Alert> : <Box>Are you sure you want to delete this DNS record?</Box>}
      <div><Box variant="strong">Record name</Box><Box>{record.name}</Box></div>
      <div><Box variant="strong">Record type</Box><Box>{record.record_type}</Box></div>
      <div><Box variant="strong">Value</Box><RecordValuesCell values={record.values} /></div>
      <Box>This action cannot be undone.</Box>
    </SpaceBetween>
  </Modal>;
}
