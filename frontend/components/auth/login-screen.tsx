"use client";

import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input, { type InputProps } from "@cloudscape-design/components/input";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { safeReturnTo } from "@/lib/auth/redirects";
import { AuthLoading } from "./auth-status";

function signInError(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) return "Invalid email or password.";
  if (error instanceof ApiError && error.status === 422) return "Check your email and password, then try again.";
  return "The authentication service could not be reached. Please try again.";
}

export function LoginScreen() {
  const { status, error: sessionError, login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const destination = safeReturnTo(searchParams.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const pending = useRef(false);
  const emailRef = useRef<InputProps.Ref>(null);
  const passwordRef = useRef<InputProps.Ref>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (status === "authenticated") router.replace(destination);
  }, [status, destination, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const normalizedEmail = email.trim().toLowerCase();
    const invalidEmail = !normalizedEmail
      ? "Enter your email address."
      : !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)
        ? "Enter a valid email address."
        : "";
    const invalidPassword = password ? "" : "Enter your password.";
    setEmailError(invalidEmail);
    setPasswordError(invalidPassword);
    setError(null);
    if (invalidEmail || invalidPassword) {
      (invalidEmail ? emailRef : passwordRef).current?.focus();
      return;
    }
    pending.current = true;
    setSubmitting(true);
    setPassword(""); // Keep no password in component state during/after the request.
    try {
      await login({ email: normalizedEmail, password });
    } catch (failure: unknown) {
      if (mounted.current) setError(signInError(failure));
    } finally {
      pending.current = false;
      if (mounted.current) setSubmitting(false);
    }
  }

  if (status === "checking" || status === "authenticated") return <AuthLoading />;

  return (
    <div className="login-page">
      <header className="login-header">
        <span className="login-brand">AWS</span>
        <span className="login-product">Route 53 Clone</span>
      </header>
      <main className="login-main">
        <SpaceBetween size="l">
          <form onSubmit={submit} noValidate>
            <Container>
              <Form header={<Header variant="h1" description="Sign in to the Route 53 console.">Sign in</Header>}>
                <SpaceBetween size="l">
                  {(error || sessionError) && (
                    <div role="alert">
                      <Alert type="error" header={error === "Invalid email or password." ? "Sign-in failed" : "Unable to sign in"}>
                        {error || sessionError}
                      </Alert>
                    </div>
                  )}
                  <FormField label="Email" controlId="login-email" errorText={emailError}>
                    <Input ref={emailRef} controlId="login-email" name="email" type="email"
                      value={email} onChange={({ detail }) => setEmail(detail.value)}
                      autoComplete="username" disableBrowserAutocorrect spellcheck={false}
                      ariaRequired readOnly={submitting} />
                  </FormField>
                  <FormField label="Password" controlId="login-password" errorText={passwordError}>
                    <Input ref={passwordRef} controlId="login-password" name="password" type="password"
                      value={password} onChange={({ detail }) => setPassword(detail.value)}
                      autoComplete="current-password" spellcheck={false}
                      ariaRequired readOnly={submitting} />
                  </FormField>
                  <Button variant="primary" formAction="submit" fullWidth loading={submitting} loadingText="Signing in">
                    Sign in
                  </Button>
                </SpaceBetween>
              </Form>
            </Container>
          </form>
          <Box color="text-body-secondary" fontSize="body-s">
            <Box variant="strong" color="inherit">Demo environment</Box>
            <div>Use the demo credentials provided in the project README.</div>
          </Box>
        </SpaceBetween>
      </main>
    </div>
  );
}
