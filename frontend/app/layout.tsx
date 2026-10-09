import type { Metadata } from "next";
import type { ReactNode } from "react";
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
      <body><AuthProvider>{children}</AuthProvider></body>
    </html>
  );
}
