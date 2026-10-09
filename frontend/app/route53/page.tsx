import { Route53Dashboard } from "@/components/dashboard/route53-dashboard";
import { ROUTE53_PAGES } from "@/lib/constants/navigation";

export const metadata = { title: ROUTE53_PAGES.dashboard.title };

export default function Route53Page() {
  return <Route53Dashboard />;
}
