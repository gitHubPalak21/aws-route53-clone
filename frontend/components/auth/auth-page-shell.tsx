import type { ReactNode } from "react";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import { ConsoleFooter } from "@/components/layout/console-footer";

export function AuthPageShell({ children }: { children: ReactNode }) {
  return <div className="login-page">
    <header>
      <TopNavigation visualContext="top-navigation" identity={{ title: "AWS", href: "/login" }}
        utilities={[{ type: "button", text: "Route 53", href: "/login" }]} />
    </header>
    <main className="login-main">{children}</main>
    <ConsoleFooter />
  </div>;
}
