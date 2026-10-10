"use client";

import Alert from "@cloudscape-design/components/alert";
import Button from "@cloudscape-design/components/button";
import ButtonDropdown from "@cloudscape-design/components/button-dropdown";
import Icon from "@cloudscape-design/components/icon";
import Input from "@cloudscape-design/components/input";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { ROUTE53_PAGES } from "@/lib/constants/navigation";
import { AwsLogo } from "@/components/layout/aws-logo";

export function AwsTopNavigation() {
  const router = useRouter();
  const homeHref = ROUTE53_PAGES.dashboard.href;
  const { user, logout, isSigningOut } = useAuth();
  const [logoutError, setLogoutError] = useState(false);

  async function signOut() {
    setLogoutError(false);
    try { await logout(); } catch { setLogoutError(true); }
  }

  return <header id="console-header" className="console-header">
    <TopNavigation visualContext="top-navigation">
      <nav className="console-topbar" aria-label="AWS console navigation">
        <Button variant="inline-link" href={homeHref} onFollow={(event) => {
          event.preventDefault(); router.push(homeHref);
        }}><AwsLogo /></Button>
        <span className="console-service-mark" title="Route 53"><Icon name="globe" ariaLabel="Route 53 service" /></span>
        <ButtonDropdown variant="icon" iconName="grid-view" ariaLabel="Services"
          items={[{ id: "route53", text: "Route 53", href: homeHref }]}
          onItemFollow={(event) => { event.preventDefault(); router.push(homeHref); }} />
        <div className="console-search-input"><Input type="search" value="" readOnly
          ariaLabel="Console search unavailable in this demonstration" placeholder="Search" /></div>
        <div className="console-topbar-utilities">
          <span className="console-topbar-optional"><ButtonDropdown variant="icon" iconName="command-prompt" ariaLabel="CloudShell"
            items={[{ id: "cloudshell", text: "CloudShell is outside this demonstration", disabled: true }]} /></span>
          <span className="console-topbar-optional"><ButtonDropdown variant="icon" iconName="notification" ariaLabel="Notifications"
            items={[{ id: "notifications", text: "No console notifications", disabled: true }]} /></span>
          <span className="console-topbar-docs"><Button variant="icon" iconName="status-info" ariaLabel="Route 53 documentation (opens in a new tab)"
            href="https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/Welcome.html" target="_blank" /></span>
          <span className="console-topbar-optional"><ButtonDropdown variant="icon" iconName="settings" ariaLabel="Console settings"
            items={[{ id: "dark", text: "Appearance: Dark", disabled: true }, { id: "compact", text: "Content density: Compact", disabled: true }]} /></span>
          <ButtonDropdown ariaLabel="Region: Global" items={[{ id: "global", text: "Route 53 is a global service", disabled: true }]}>Global</ButtonDropdown>
          <ButtonDropdown ariaLabel={`${user?.display_name} account menu`}
            items={[{ id: "signout", text: isSigningOut ? "Signing out…" : "Sign out", disabled: isSigningOut }]}
            onItemClick={(event) => { if (event.detail.id === "signout") void signOut(); }}>
            <span className="console-account-name">{user?.display_name}</span>
          </ButtonDropdown>
        </div>
      </nav>
    </TopNavigation>
    {logoutError && <div role="alert"><Alert type="error" header="Unable to sign out" dismissible
      onDismiss={() => setLogoutError(false)} i18nStrings={{ dismissAriaLabel: "Dismiss sign-out error" }}>
      Your session is still active. Please try signing out again.
    </Alert></div>}
  </header>;
}
