import { DNSRecordEditor } from "@/components/dns-records/dns-record-editor";

export const metadata = { title: "Create record" };

export default async function CreateRecordPage({ params }: { params: Promise<{ zoneId: string }> }) {
  const { zoneId } = await params;
  return <DNSRecordEditor zoneId={zoneId} />;
}
