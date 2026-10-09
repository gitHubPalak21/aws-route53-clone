"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/hooks/use-auth";
import { AuthLoading, AuthUnavailable } from "./auth-status";

export function HomeRedirect() {
  const { status, error, refreshUser } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (status === "authenticated") router.replace("/route53");
    if (status === "unauthenticated") router.replace("/login");
  }, [status, router]);

  return status === "error"
    ? <AuthUnavailable message={error} onRetry={() => void refreshUser()} />
    : <AuthLoading />;
}
