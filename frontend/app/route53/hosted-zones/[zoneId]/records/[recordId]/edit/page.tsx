import { DNSRecordEditor } from "@/components/dns-records/dns-record-editor";

export const metadata = { title: "Edit record" };

export default async function EditRecordPage({ params }: { params: Promise<{ zoneId: string; recordId: string }> }) {
  const { zoneId, recordId } = await params;
  return <DNSRecordEditor zoneId={zoneId} recordId={recordId} />;
}
