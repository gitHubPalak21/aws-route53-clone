"use client";

import BreadcrumbGroup, {
  type BreadcrumbGroupProps,
} from "@cloudscape-design/components/breadcrumb-group";
import { usePathname, useRouter } from "next/navigation";
import { useHostedZoneContext } from "@/components/hosted-zones/hosted-zone-context";
import { hostedZonePath } from "@/lib/api/hosted-zones";
import {
  ROUTE53_PAGES,
  type Route53PageDefinition,
} from "@/lib/constants/navigation";

export function Route53Breadcrumbs({ page }: { page: Route53PageDefinition }) {
  const router = useRouter();
  const pathname = usePathname();
  const { resource } = useHostedZoneContext();
  const home = ROUTE53_PAGES.dashboard;
  const items: BreadcrumbGroupProps.Item[] = [{ text: home.title, href: home.href }];
  if (page.href !== home.href) {
    items.push({ text: page.title, href: page.href });
  }
  if (page.href === ROUTE53_PAGES.hostedZones.href && pathname !== page.href) {
    const [id, action, recordAction, recordSubAction] = pathname.slice(page.href.length + 1).split("/");
    if (id === "create") items.push({ text: "Create hosted zone", href: pathname });
    else if (id) {
      items.push({ text: resource?.id === id ? resource.name : "Hosted zone", href: hostedZonePath(id) });
      if (action === "edit") items.push({ text: "Edit", href: pathname });
      if (action === "records" && recordAction === "create") items.push({ text: "Create record", href: pathname });
      if (action === "records" && recordSubAction === "edit") items.push({ text: "Edit record", href: pathname });
    }
  }

  return (
    <BreadcrumbGroup
      ariaLabel="Breadcrumbs"
      expandAriaLabel="Show all breadcrumbs"
      items={items}
      onFollow={(event) => {
        event.preventDefault();
        router.push(event.detail.href);
      }}
    />
  );
}
