"use client";

import Alert from "@cloudscape-design/components/alert";
import Button from "@cloudscape-design/components/button";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import { useRouter } from "next/navigation";
import { useNotifications } from "@/components/notifications/notification-provider";
import { HostedZoneResourceState } from "@/components/hosted-zones/hosted-zone-resource-state";
import { useHostedZone } from "@/hooks/use-hosted-zone";
import { useDNSRecord } from "@/hooks/use-dns-records";
import { createDNSRecord, updateDNSRecord } from "@/lib/api/dns-records";
import { hostedZonePath } from "@/lib/api/hosted-zones";
import type { DNSRecord } from "@/types/dns-record";
import { DNSRecordForm } from "./dns-record-form";

export function DNSRecordEditor({ zoneId, recordId }: { zoneId: string; recordId?: string }) {
  const router = useRouter();
  const { success } = useNotifications();
  const { zone, loading, error, refetch } = useHostedZone(zoneId);
  const detail = useDNSRecord(zoneId, recordId);
  const title = recordId ? "Edit record" : "Create record";
  function saved(record: DNSRecord) {
    success(`Record ${record.name} was ${recordId ? "updated" : "created"} successfully.`);
    router.push(hostedZonePath(zoneId));
  }
  if (!zone) return <HostedZoneResourceState loading={loading} missing={error === "missing"} onRetry={refetch} />;
  if (recordId && (!detail.record || detail.record.is_system)) return <ContentLayout disableOverlap header={<Header variant="h1">{detail.error === "missing" ? "Record not found" : title}</Header>}>
    <SpaceBetween size="m">
      {detail.isLoading ? <div role="status"><Spinner /> Loading record</div>
        : <Alert type={detail.record?.is_system ? "info" : "error"} header={detail.error === "failed" ? "Unable to load record" : undefined}
          action={detail.error === "failed" ? <Button onClick={detail.refetch}>Retry</Button> : undefined}>
          {detail.record?.is_system ? "This record is managed by the system and cannot be edited."
            : detail.error === "missing" ? "The record may have been deleted or you may not have access to it." : "The record could not be loaded. Try again."}
        </Alert>}
      <Button onClick={() => router.push(hostedZonePath(zoneId))}>Back to hosted zone</Button>
    </SpaceBetween>
  </ContentLayout>;
  return <DNSRecordForm key={`${zone.id}:${recordId ?? "create"}`} mode={recordId ? "edit" : "create"} hostedZone={zone} initialRecord={detail.record ?? undefined}
    onSubmit={(payload) => recordId ? updateDNSRecord(zoneId, recordId, payload) : createDNSRecord(zoneId, payload)} onSuccess={saved} />;
}
