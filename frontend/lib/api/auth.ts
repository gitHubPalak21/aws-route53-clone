import { ApiError, apiRequest } from "@/lib/api/client";
import type { AuthResponse, AuthUser, LoginCredentials } from "@/types/auth";

function publicUser(response: AuthResponse | undefined): AuthUser {
  if (!response?.user) {
    throw new ApiError("The authentication service returned an invalid response.", 502);
  }
  return response.user;
}

export async function login(credentials: LoginCredentials): Promise<void> {
  publicUser(await apiRequest<AuthResponse>("/api/auth/login", {
    method: "POST",
    json: { email: credentials.email, password: credentials.password },
  }));
}

export async function getCurrentUser(): Promise<AuthUser> {
  return publicUser(await apiRequest<AuthResponse>("/api/auth/me", { cache: "no-store" }));
}

export async function logout(): Promise<void> {
  await apiRequest("/api/auth/logout", { method: "POST" });
}
