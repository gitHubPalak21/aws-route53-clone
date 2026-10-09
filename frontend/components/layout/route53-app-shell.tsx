"use client";

import AppLayout, {
  type AppLayoutProps,
} from "@cloudscape-design/components/app-layout";
import { usePathname } from "next/navigation";
import { useRef, type ReactNode } from "react";
import { getRoute53Page } from "@/lib/constants/navigation";
import { AwsTopNavigation } from "./aws-top-navigation";
import { Route53Breadcrumbs } from "./route53-breadcrumbs";
import { Route53SideNavigation } from "./route53-side-navigation";
import { ConsoleNotifications } from "@/components/notifications/notification-provider";

export function Route53AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const page = getRoute53Page(pathname);
  const layoutRef = useRef<AppLayoutProps.Ref>(null);
  const contentType: AppLayoutProps.ContentType = /\/(create|edit)$/.test(pathname)
    ? "form" : pathname === "/route53/hosted-zones" ? "table"
    : pathname === "/route53" ? "dashboard" : "default";

  return (
    <>
      <AwsTopNavigation />
      <AppLayout
        key={contentType}
        ref={layoutRef}
        headerSelector="#console-header"
        contentType={contentType}
        maxContentWidth={contentType === "form" ? 800 : undefined}
        toolsHide
        navigation={
          <Route53SideNavigation
            activeHref={page.href}
            onNavigate={() => layoutRef.current?.closeNavigationIfNecessary()}
          />
        }
        breadcrumbs={<Route53Breadcrumbs page={page} />}
        notifications={<ConsoleNotifications />}
        content={children}
        ariaLabels={{
          navigation: "Route 53 navigation",
          navigationToggle: "Open Route 53 navigation",
          navigationClose: "Close Route 53 navigation",
        }}
      />
    </>
  );
}
