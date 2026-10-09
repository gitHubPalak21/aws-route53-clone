import { Route53PageContent } from "@/components/common/route53-page-content";
import { ROUTE53_PAGES } from "@/lib/constants/navigation";

export const metadata = { title: ROUTE53_PAGES.trafficPolicies.title };

export default function TrafficPoliciesPage() {
  return <Route53PageContent page={ROUTE53_PAGES.trafficPolicies} />;
}
