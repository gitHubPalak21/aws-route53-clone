import type { Metadata } from "next";
import type { CSSProperties, ReactNode } from "react";
import { colorBackgroundLayoutMain, spaceStaticXs, spaceStaticS, spaceStaticM, spaceStaticL, spaceStaticXl, spaceStaticXxl } from "@cloudscape-design/design-tokens";
import { AuthProvider } from "@/components/auth/auth-provider";
import "@cloudscape-design/global-styles/index.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Route 53 Clone", template: "%s | Route 53 Clone" },
  description: "An AWS Route 53 console UI and workflow clone.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body style={{
        "--console-background": colorBackgroundLayoutMain,
        "--console-space-xs": spaceStaticXs,
        "--console-space-s": spaceStaticS,
        "--console-space-m": spaceStaticM,
        "--console-space-l": spaceStaticL,
        "--console-space-xl": spaceStaticXl,
        "--console-space-xxl": spaceStaticXxl,
      } as CSSProperties}><AuthProvider>{children}</AuthProvider></body>
    </html>
  );
}
