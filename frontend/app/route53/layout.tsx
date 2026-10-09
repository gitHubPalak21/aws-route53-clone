import type { ReactNode } from "react";
import { Route53AppShell } from "@/components/layout/route53-app-shell";
import { AuthGuard } from "@/components/auth/auth-guard";
import { NotificationProvider } from "@/components/notifications/notification-provider";
import { HostedZoneContextProvider } from "@/components/hosted-zones/hosted-zone-context";

export default function Route53Layout({ children }: { children: ReactNode }) {
  return <AuthGuard><NotificationProvider><HostedZoneContextProvider>
    <Route53AppShell>{children}</Route53AppShell>
  </HostedZoneContextProvider></NotificationProvider></AuthGuard>;
}
