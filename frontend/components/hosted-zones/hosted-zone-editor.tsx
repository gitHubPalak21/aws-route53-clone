"use client";

import { useRouter } from "next/navigation";
import { useNotifications } from "@/components/notifications/notification-provider";
import { useHostedZone } from "@/hooks/use-hosted-zone";
import { createHostedZone, hostedZonePath, updateHostedZone } from "@/lib/api/hosted-zones";
import type { HostedZone } from "@/types/hosted-zone";
import { HostedZoneForm } from "./hosted-zone-form";
import { HostedZoneResourceState } from "./hosted-zone-resource-state";
import { useHostedZoneContext } from "./hosted-zone-context";

function useSavedZone(verb: "created" | "updated") {
  const router = useRouter();
  const { success } = useNotifications();
  const { setResource } = useHostedZoneContext();
  return (zone: HostedZone) => {
    setResource({ id: zone.id, name: zone.name });
    success(`Hosted zone ${zone.name} was ${verb} successfully.`);
    router.push(hostedZonePath(zone.id));
  };
}

export function CreateHostedZone() {
  const onSuccess = useSavedZone("created");
  return <HostedZoneForm mode="create" cancelHref="/route53/hosted-zones" onSubmit={createHostedZone} onSuccess={onSuccess} />;
}

export function EditHostedZone({ zoneId }: { zoneId: string }) {
  const { zone, loading, error, refetch } = useHostedZone(zoneId);
  const onSuccess = useSavedZone("updated");
  if (!zone) return <HostedZoneResourceState loading={loading} missing={error === "missing"} onRetry={refetch} />;
  return <HostedZoneForm key={zone.id} mode="edit" initialZone={zone} cancelHref={hostedZonePath(zone.id)}
    onSubmit={(payload) => updateHostedZone(zone.id, payload)} onSuccess={onSuccess} />;
}
