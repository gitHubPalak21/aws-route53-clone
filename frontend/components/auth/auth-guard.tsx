"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "@/hooks/use-auth";
import { loginDestination } from "@/lib/auth/redirects";
import { AuthLoading, AuthUnavailable } from "./auth-status";

export function AuthGuard({ children }: { children: ReactNode }) {
  const { status, error, signedOut, refreshUser } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(signedOut ? "/login" : loginDestination(pathname));
    }
  }, [status, signedOut, pathname, router]);

  if (status === "error") {
    return <AuthUnavailable message={error} onRetry={() => void refreshUser()} />;
  }
  if (status !== "authenticated") return <AuthLoading />;
  return children;
}
