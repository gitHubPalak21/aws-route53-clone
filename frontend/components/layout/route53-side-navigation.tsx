"use client";

import SideNavigation from "@cloudscape-design/components/side-navigation";
import { useRouter } from "next/navigation";
import { ROUTE53_NAV_ITEMS, ROUTE53_PAGES } from "@/lib/constants/navigation";

interface Route53SideNavigationProps {
  activeHref: string;
  onNavigate: () => void;
}

export function Route53SideNavigation({
  activeHref,
  onNavigate,
}: Route53SideNavigationProps) {
  const router = useRouter();

  return (
    <SideNavigation
      header={{ text: "Route 53", href: ROUTE53_PAGES.dashboard.href }}
      activeHref={activeHref}
      items={ROUTE53_NAV_ITEMS}
      onFollow={(event) => {
        if (!event.detail.external) {
          event.preventDefault();
          router.push(event.detail.href);
          onNavigate();
        }
      }}
    />
  );
}
