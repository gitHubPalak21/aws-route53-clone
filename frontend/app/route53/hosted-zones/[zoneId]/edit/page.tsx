import { EditHostedZone } from "@/components/hosted-zones/hosted-zone-editor";

export const metadata = { title: "Edit hosted zone" };

export default async function EditHostedZonePage({ params }: { params: Promise<{ zoneId: string }> }) {
  const { zoneId } = await params;
  return <EditHostedZone zoneId={zoneId} />;
}
