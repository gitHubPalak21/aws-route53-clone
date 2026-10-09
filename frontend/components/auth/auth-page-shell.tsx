import type { ReactNode } from "react";

export function AuthPageShell({ children }: { children: ReactNode }) {
  return <div className="login-page">
    <header className="login-header">
      <span className="login-brand">AWS</span>
      <span className="login-product">Route 53 Clone</span>
    </header>
    <main className="login-main">{children}</main>
  </div>;
}
