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
import { deleteHostedZone } from "@/lib/api/hosted-zones";
import type { HostedZone } from "@/types/hosted-zone";

export function DeleteHostedZoneModal({ zone, onDismiss, onDeleted }: {
  zone: HostedZone; onDismiss: () => void; onDeleted: () => void;
}) {
  const { success } = useNotifications();
  const { refreshUser } = useAuth();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  async function confirm() {
    if (pending.current) return;
    pending.current = true;
    setDeleting(true); setError(null);
    let deleted = false;
    try {
      await deleteHostedZone(zone.id);
      deleted = true;
      if (mounted.current) {
        success(`Hosted zone ${zone.name} deleted.`);
        onDeleted();
      }
    } catch (failure: unknown) {
      if (!mounted.current) return;
      if (failure instanceof ApiError && failure.status === 401) { void refreshUser(); return; }
      setError(failure instanceof ApiError && failure.status === 404
        ? "The hosted zone no longer exists or you don't have access to it."
        : "The hosted zone could not be deleted. Try again.");
    } finally {
      if (!deleted) {
        pending.current = false;
        if (mounted.current) setDeleting(false);
      }
    }
  }

  return <Modal visible header="Delete hosted zone?" closeAriaLabel="Close delete confirmation"
    onDismiss={() => { if (!pending.current) onDismiss(); }}
    footer={<Box float="right"><SpaceBetween direction="horizontal" size="xs">
      <Button variant="link" formAction="none" disabled={deleting} onClick={onDismiss}>Cancel</Button>
      <Button variant="primary" loading={deleting} loadingText="Deleting hosted zone" onClick={() => void confirm()}>Delete</Button>
    </SpaceBetween></Box>}>
    <SpaceBetween size="m">
      {error && <div role="alert"><Alert type="error" header="Unable to delete hosted zone">{error}</Alert></div>}
      <Box>Are you sure you want to delete hosted zone <Box variant="strong">{zone.name}</Box>?</Box>
      <div><Box variant="strong">Hosted zone ID</Box><Box>{zone.id}</Box></div>
      <Box>This action cannot be undone. The hosted zone and its associated records will be removed.</Box>
    </SpaceBetween>
  </Modal>;
}
