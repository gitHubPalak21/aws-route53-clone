"use client";

import ButtonDropdown from "@cloudscape-design/components/button-dropdown";
import Input from "@cloudscape-design/components/input";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import Alert from "@cloudscape-design/components/alert";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { ROUTE53_PAGES } from "@/lib/constants/navigation";

export function AwsTopNavigation() {
  const router = useRouter();
  const homeHref = ROUTE53_PAGES.dashboard.href;
  const { user, logout, isSigningOut } = useAuth();
  const [logoutError, setLogoutError] = useState(false);

  async function signOut() {
    setLogoutError(false);
    try {
      await logout();
    } catch {
      setLogoutError(true);
    }
  }

  return (
    <header id="console-header" className="console-header">
      <TopNavigation
        visualContext="top-navigation"
        identity={{
          title: "AWS",
          href: homeHref,
          onFollow: (event) => {
            event.preventDefault();
            router.push(homeHref);
          },
        }}
        search={
          <div className="console-search">
            <ButtonDropdown
              variant="normal"
              ariaLabel="Services"
              items={[
                { id: "route53", text: "Route 53", href: homeHref },
              ]}
              onItemFollow={(event) => {
                event.preventDefault();
                router.push(homeHref);
              }}
            >
              Services
            </ButtonDropdown>
            <div className="console-search-input">
              <Input
                type="search"
                value=""
                disabled
                ariaLabel="Console search unavailable in this demonstration"
                placeholder="Search"
              />
            </div>
          </div>
        }
        utilities={[
          {
            type: "button",
            iconName: "status-info",
            ariaLabel: "Route 53 documentation (opens in a new tab)",
            href: "https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/Welcome.html",
            target: "_blank",
          },
          {
            type: "menu-dropdown",
            text: "Global",
            title: "Global service",
            ariaLabel: "Region: Global",
            items: [
              { id: "global", text: "Route 53 is a global service", disabled: true },
            ],
          },
          {
            type: "menu-dropdown",
            text: user?.display_name,
            title: user?.display_name,
            description: user?.email,
            iconName: "user-profile",
            ariaLabel: `${user?.display_name} account menu`,
            items: [
              { id: "signout", text: isSigningOut ? "Signing out…" : "Sign out", disabled: isSigningOut },
            ],
            onItemClick: (event) => {
              if (event.detail.id === "signout") void signOut();
            },
          },
        ]}
        i18nStrings={{
          searchIconAriaLabel: "Open console search and services",
          searchDismissIconAriaLabel: "Close console search and services",
          overflowMenuTriggerText: "More",
          overflowMenuTitleText: "Console navigation",
          overflowMenuBackIconAriaLabel: "Back",
          overflowMenuDismissIconAriaLabel: "Close console navigation",
        }}
      />
      {logoutError && (
        <div role="alert">
          <Alert type="error" header="Unable to sign out" dismissible onDismiss={() => setLogoutError(false)}
            i18nStrings={{ dismissAriaLabel: "Dismiss sign-out error" }}>
            Your session is still active. Please try signing out again.
          </Alert>
        </div>
      )}
    </header>
  );
}
