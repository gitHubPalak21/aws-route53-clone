"use client";

import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input, { type InputProps } from "@cloudscape-design/components/input";
import Link from "@cloudscape-design/components/link";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useAuth } from "@/hooks/use-auth";
import { registrationError, registrationPayload, validateSignup, type SignupErrors, type SignupValues } from "@/lib/auth/registration";
import { AuthLoading } from "./auth-status";
import { AuthPageShell } from "./auth-page-shell";

const empty: SignupValues = { display_name: "", email: "", password: "", confirm_password: "" };
const fields = [
  { key: "display_name", label: "Name", type: "text", autoComplete: "name" },
  { key: "email", label: "Email", type: "email", autoComplete: "username" },
  { key: "password", label: "Password", type: "password", autoComplete: "new-password" },
  { key: "confirm_password", label: "Confirm password", type: "password", autoComplete: "new-password" },
] as const;

export function SignupScreen() {
  const { status, error: sessionError, register } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<SignupValues>(empty);
  const [errors, setErrors] = useState<SignupErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const pending = useRef(false);
  const mounted = useRef(true);
  const controls = useRef<Partial<Record<keyof SignupValues, InputProps.Ref | null>>>({});

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  useEffect(() => {
    if (status === "authenticated") router.replace("/route53");
  }, [status, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const invalid = validateSignup(values);
    setErrors(invalid);
    setError(null);
    const first = fields.find(({ key }) => invalid[key]);
    if (first) { controls.current[first.key]?.focus(); return; }
    pending.current = true;
    setSubmitting(true);
    const payload = registrationPayload(values);
    setValues((previous) => ({ ...previous, password: "", confirm_password: "" }));
    try {
      await register(payload);
    } catch (failure: unknown) {
      if (mounted.current) {
        const feedback = registrationError(failure);
        setErrors(feedback.fields);
        setError(feedback.message);
      }
    } finally {
      pending.current = false;
      if (mounted.current) setSubmitting(false);
    }
  }

  if (status === "checking" || status === "authenticated") return <AuthLoading />;

  return <AuthPageShell><SpaceBetween size="l">
    <form onSubmit={submit} noValidate>
      <Container>
        <Form header={<Header variant="h1" description="Create an account to access the Route 53 console.">Create account</Header>}>
          <SpaceBetween size="l">
            {(error || sessionError) && <div role="alert"><Alert type="error" header="Unable to create account">{error || sessionError}</Alert></div>}
            {fields.map(({ key, label, type, autoComplete }) => <FormField key={key} label={label} controlId={`signup-${key}`}
              errorText={errors[key]} constraintText={key === "password" ? "Use at least 8 characters." : undefined}>
              <Input ref={(control) => { controls.current[key] = control; }} controlId={`signup-${key}`} name={key} type={type}
                value={values[key]} onChange={({ detail }) => setValues((previous) => ({ ...previous, [key]: detail.value }))}
                autoComplete={autoComplete} disableBrowserAutocorrect spellcheck={false} ariaRequired readOnly={submitting} />
            </FormField>)}
            <Button variant="primary" formAction="submit" fullWidth loading={submitting} loadingText="Creating account">Create account</Button>
          </SpaceBetween>
        </Form>
      </Container>
    </form>
    <Box>Already have an account? <Link href="/login" onFollow={(event) => { event.preventDefault(); router.push("/login"); }}>Sign in</Link></Box>
  </SpaceBetween></AuthPageShell>;
}
