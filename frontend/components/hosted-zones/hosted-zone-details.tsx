"use client";

import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Header from "@cloudscape-design/components/header";
import KeyValuePairs from "@cloudscape-design/components/key-value-pairs";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { DNSRecordsTable } from "@/components/dns-records/dns-records-table";
import { useHostedZone } from "@/hooks/use-hosted-zone";
import { hostedZonePath } from "@/lib/api/hosted-zones";
import { regionLabel } from "@/lib/constants/regions";
import { HOSTED_ZONE_TYPE_LABELS } from "@/types/hosted-zone";
import { DeleteHostedZoneModal } from "./delete-hosted-zone-modal";
import { HostedZoneResourceState } from "./hosted-zone-resource-state";

export function HostedZoneDetails({ zoneId }: { zoneId: string }) {
  const router = useRouter();
  const { zone, loading, error, refetch } = useHostedZone(zoneId, true);
  const [deleteVisible, setDeleteVisible] = useState(false);
  const [missingRecordsZone, setMissingRecordsZone] = useState<string | null>(null);
  const onZoneMissing = useCallback(() => setMissingRecordsZone(zoneId), [zoneId]);
  if (missingRecordsZone === zoneId) return <HostedZoneResourceState loading={false} missing onRetry={refetch} />;
  if (!zone) return <HostedZoneResourceState loading={loading} missing={error === "missing"} onRetry={refetch} />;
  return <ContentLayout disableOverlap header={<Header variant="h1" actions={
    <SpaceBetween direction="horizontal" size="xs">
      <Button onClick={() => router.push(`${hostedZonePath(zone.id)}/edit`)}>Edit</Button>
      <Button onClick={() => setDeleteVisible(true)}>Delete</Button>
    </SpaceBetween>}>{zone.name}</Header>}>
    <SpaceBetween size="l"><Container header={<Header variant="h2">Hosted zone details</Header>}>
      <KeyValuePairs columns={zone.zone_type === "PUBLIC" ? 4 : 3} minColumnWidth={240} items={[
        { label: "Hosted zone ID", value: zone.id },
        { label: "Type", value: `${HOSTED_ZONE_TYPE_LABELS[zone.zone_type]} hosted zone` },
        { label: "Description", value: zone.comment || "—" },
        { label: "Record count", value: String(zone.record_count) },
        ...(zone.zone_type === "PRIVATE" ? [
          { label: "Region", value: zone.region ? regionLabel(zone.region) : "—" },
          { label: "VPC ID", value: zone.vpc_id || "—" },
        ] : []),
      ]} />
    </Container>
    <DNSRecordsTable key={zoneId} zoneId={zoneId} zoneRecordCount={zone.record_count} onZoneMissing={onZoneMissing} onCountChanged={refetch} />
    </SpaceBetween>
    {deleteVisible && <DeleteHostedZoneModal zone={zone} onDismiss={() => setDeleteVisible(false)}
      onDeleted={() => router.replace("/route53/hosted-zones")} />}
  </ContentLayout>;
}
