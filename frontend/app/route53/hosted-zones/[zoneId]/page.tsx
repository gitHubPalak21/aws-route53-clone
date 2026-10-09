import { HostedZoneDetails } from "@/components/hosted-zones/hosted-zone-details";

export const metadata = { title: "Hosted zone details" };

export default async function HostedZoneDetailPage({ params }: { params: Promise<{ zoneId: string }> }) {
  const { zoneId } = await params;
  return <HostedZoneDetails zoneId={zoneId} />;
}
