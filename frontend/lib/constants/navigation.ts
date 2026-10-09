import type { SideNavigationProps } from "@cloudscape-design/components/side-navigation";

export interface Route53PageDefinition {
  href: string;
  title: string;
  navigationLabel: string;
  description: string;
}

export const ROUTE53_PAGES = {
  dashboard: {
    href: "/route53",
    title: "Route 53",
    navigationLabel: "Dashboard",
    description: "Manage hosted zones and DNS records in this Route 53 clone.",
  },
  hostedZones: {
    href: "/route53/hosted-zones",
    title: "Hosted zones",
    navigationLabel: "Hosted zones",
    description: "Create and manage public and private hosted zones.",
  },
  healthChecks: {
    href: "/route53/health-checks",
    title: "Health checks",
    navigationLabel: "Health checks",
    description: "Health check management is not implemented in this demonstration.",
  },
  trafficPolicies: {
    href: "/route53/traffic-policies",
    title: "Traffic policies",
    navigationLabel: "Traffic policies",
    description: "Traffic policy management is not implemented in this demonstration.",
  },
  resolver: {
    href: "/route53/resolver",
    title: "Resolver",
    navigationLabel: "Resolver",
    description: "Resolver functionality is not implemented in this demonstration.",
  },
  profiles: {
    href: "/route53/profiles",
    title: "Profiles",
    navigationLabel: "Profiles",
    description: "Profiles functionality is not implemented in this demonstration.",
  },
} as const satisfies Record<string, Route53PageDefinition>;

function navigationLink(page: Route53PageDefinition): SideNavigationProps.Link {
  return { type: "link", text: page.navigationLabel, href: page.href };
}

export const ROUTE53_NAV_ITEMS: ReadonlyArray<SideNavigationProps.Item> = [
  navigationLink(ROUTE53_PAGES.dashboard),
  { type: "divider" },
  {
    type: "section",
    text: "DNS management",
    items: [navigationLink(ROUTE53_PAGES.hostedZones)],
  },
  navigationLink(ROUTE53_PAGES.healthChecks),
  {
    type: "section",
    text: "Traffic flow",
    items: [navigationLink(ROUTE53_PAGES.trafficPolicies)],
  },
  navigationLink(ROUTE53_PAGES.resolver),
  navigationLink(ROUTE53_PAGES.profiles),
];

/** Nested resource routes will retain their parent navigation selection. */
export function getRoute53Page(pathname: string): Route53PageDefinition {
  return (
    Object.values(ROUTE53_PAGES).find(
      (page) =>
        pathname === page.href ||
        (page.href !== ROUTE53_PAGES.dashboard.href &&
          pathname.startsWith(`${page.href}/`)),
    ) ?? ROUTE53_PAGES.dashboard
  );
}
