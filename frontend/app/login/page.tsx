import { Suspense } from "react";
import { LoginScreen } from "@/components/auth/login-screen";
import { AuthLoading } from "@/components/auth/auth-status";

export const metadata = { title: "Sign in" };

export default function LoginPage() {
  return <Suspense fallback={<AuthLoading />}><LoginScreen /></Suspense>;
}
