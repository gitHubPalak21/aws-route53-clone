import { Route53PageContent } from "@/components/common/route53-page-content";
import { ROUTE53_PAGES } from "@/lib/constants/navigation";

export const metadata = { title: ROUTE53_PAGES.profiles.title };

export default function ProfilesPage() {
  return <Route53PageContent page={ROUTE53_PAGES.profiles} />;
}
