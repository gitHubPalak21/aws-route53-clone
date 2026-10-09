import type { ReactNode } from "react";
import TopNavigation from "@cloudscape-design/components/top-navigation";

export function AuthPageShell({ children }: { children: ReactNode }) {
  return <div className="login-page">
    <header>
      <TopNavigation visualContext="top-navigation" identity={{ title: "AWS", href: "/login" }}
        search={<span>Route 53 Clone</span>} />
    </header>
    <main className="login-main">{children}</main>
  </div>;
}
