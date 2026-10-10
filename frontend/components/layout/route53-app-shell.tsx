"use client";

import AppLayoutToolbar, { type AppLayoutToolbarProps } from "@cloudscape-design/components/app-layout-toolbar";
import { usePathname } from "next/navigation";
import { useRef, type ReactNode } from "react";
import { getRoute53Page } from "@/lib/constants/navigation";
import { AwsTopNavigation } from "./aws-top-navigation";
import { Route53Breadcrumbs } from "./route53-breadcrumbs";
import { Route53SideNavigation } from "./route53-side-navigation";
import { ConsoleNotifications } from "@/components/notifications/notification-provider";
import { ConsoleFooter } from "./console-footer";
import { Route53HelpPanel } from "./route53-help-panel";

export function Route53AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const page = getRoute53Page(pathname);
  const layoutRef = useRef<AppLayoutToolbarProps.Ref>(null);
  const contentType: AppLayoutToolbarProps.ContentType = /\/(create|edit)$/.test(pathname)
    ? "form" : pathname === "/route53/hosted-zones" ? "table"
    : pathname === "/route53" ? "dashboard" : "default";

  return (
    <>
      <AwsTopNavigation />
      <AppLayoutToolbar
        key={contentType}
        ref={layoutRef}
        headerSelector="#console-header"
        footerSelector="#console-footer"
        contentType={contentType}
        maxContentWidth={contentType === "form" ? 800 : undefined}
        tools={<Route53HelpPanel />}
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
          tools: "Route 53 help",
          toolsToggle: "Open Route 53 help",
          toolsClose: "Close Route 53 help",
        }}
      />
      <ConsoleFooter />
    </>
  );
}
