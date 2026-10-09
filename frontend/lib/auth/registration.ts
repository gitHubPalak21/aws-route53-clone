import { ApiError } from "@/lib/api/client";
import { validationFeedback } from "@/lib/api/validation-errors";
import type { RegistrationCredentials } from "@/types/auth";

export interface SignupValues extends RegistrationCredentials { confirm_password: string }
export type SignupErrors = Partial<Record<keyof SignupValues, string>>;

export function validateSignup(values: SignupValues): SignupErrors {
  const errors: SignupErrors = {};
  const name = values.display_name.trim();
  const email = values.email.trim();
  if (!name) errors.display_name = "Enter your name.";
  else if (name.length > 128) errors.display_name = "Use 128 characters or fewer.";
  if (!email) errors.email = "Enter your email address.";
  else if (email.length > 320 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = "Enter a valid email address.";
  if (values.password.length < 8) errors.password = "Use at least 8 characters.";
  else if (values.password.length > 1024) errors.password = "Use 1024 characters or fewer.";
  if (!values.confirm_password) errors.confirm_password = "Confirm your password.";
  else if (values.confirm_password !== values.password) errors.confirm_password = "Passwords must match.";
  return errors;
}

export function registrationPayload(values: SignupValues): RegistrationCredentials {
  return { display_name: values.display_name.trim(), email: values.email.trim().toLowerCase(), password: values.password };
}

export function registrationError(error: unknown): { message: string; fields: SignupErrors } {
  if (error instanceof ApiError && error.status === 409) {
    const message = "An account with this email already exists.";
    return { message, fields: { email: message } };
  }
  if (error instanceof ApiError && (error.status === 400 || error.status === 422)) {
    const feedback = validationFeedback(error);
    const fields: SignupErrors = {};
    for (const field of ["display_name", "email", "password"] as const) {
      if (feedback.fields[field]) fields[field] = feedback.fields[field];
    }
    return { message: "Check your account details and try again.", fields };
  }
  return { message: "Unable to create your account. Please try again.", fields: {} };
}
