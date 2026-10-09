import { HostedZonesTable } from "@/components/hosted-zones/hosted-zones-table";
import { ROUTE53_PAGES } from "@/lib/constants/navigation";

export const metadata = { title: ROUTE53_PAGES.hostedZones.title };

export default function HostedZonesPage() {
  return <HostedZonesTable />;
}
