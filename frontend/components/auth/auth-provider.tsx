"use client";

import { createContext, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as authApi from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import type { AuthUser, LoginCredentials, RegistrationCredentials } from "@/types/auth";

type AuthState =
  | { status: "checking"; user: null; error: null; signedOut: false }
  | { status: "authenticated"; user: AuthUser; error: null; signedOut: false }
  | { status: "unauthenticated"; user: null; error: null; signedOut: boolean }
  | { status: "error"; user: null; error: string; signedOut: false };

type AuthContextValue = AuthState & {
  isLoading: boolean;
  isAuthenticated: boolean;
  isSigningOut: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegistrationCredentials) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

export const AuthContext = createContext<AuthContextValue | null>(null);
const checking: AuthState = { status: "checking", user: null, error: null, signedOut: false };

function failedSession(error: unknown): AuthState {
  return error instanceof ApiError && error.status === 401
    ? { status: "unauthenticated", user: null, error: null, signedOut: false }
    : { status: "error", user: null, error: "The authentication service could not be reached. Please try again.", signedOut: false };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(checking);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const mounted = useRef(false);
  const version = useRef(0);
  const pendingMe = useRef<Promise<AuthUser> | null>(null);
  const logoutPending = useRef(false);

  const requestUser = useCallback(() => {
    // Share an in-flight check, including React Strict Mode's effect replay.
    if (!pendingMe.current) {
      pendingMe.current = authApi.getCurrentUser().finally(() => {
        pendingMe.current = null;
      });
    }
    return pendingMe.current;
  }, []);

  useEffect(() => {
    mounted.current = true;
    let active = true;
    const currentVersion = version.current;
    requestUser().then(
      (user) => {
        if (active && currentVersion === version.current) {
          setState({ status: "authenticated", user, error: null, signedOut: false });
        }
      },
      (error: unknown) => {
        if (active && currentVersion === version.current) setState(failedSession(error));
      },
    );
    return () => {
      active = false;
      mounted.current = false;
    };
  }, [requestUser]);

  const refreshUser = useCallback(async () => {
    const currentVersion = ++version.current;
    setState(checking);
    try {
      const user = await requestUser();
      if (mounted.current && currentVersion === version.current) {
        setState({ status: "authenticated", user, error: null, signedOut: false });
      }
    } catch (error: unknown) {
      if (mounted.current && currentVersion === version.current) setState(failedSession(error));
    }
  }, [requestUser]);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const currentVersion = ++version.current;
    await authApi.login(credentials);
    // Confirm identity with the backend session, rather than a local signed-in flag.
    const user = await authApi.getCurrentUser();
    if (mounted.current && currentVersion === version.current) {
      setState({ status: "authenticated", user, error: null, signedOut: false });
    }
  }, []);

  const logout = useCallback(async () => {
    if (logoutPending.current) return;
    logoutPending.current = true;
    const currentVersion = ++version.current;
    setIsSigningOut(true);
    try {
      await authApi.logout();
      if (mounted.current && currentVersion === version.current) {
        setState({ status: "unauthenticated", user: null, error: null, signedOut: true });
      }
    } finally {
      // Failure leaves the user signed in so they can retry revoking the session.
      logoutPending.current = false;
      if (mounted.current) setIsSigningOut(false);
    }
  }, []);

  const register = useCallback(async (credentials: RegistrationCredentials) => {
    const currentVersion = ++version.current;
    const user = await authApi.register(credentials);
    if (mounted.current && currentVersion === version.current) {
      setState({ status: "authenticated", user, error: null, signedOut: false });
    }
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    ...state,
    isLoading: state.status === "checking",
    isAuthenticated: state.status === "authenticated",
    isSigningOut, login, register, logout, refreshUser,
  }), [state, isSigningOut, login, register, logout, refreshUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
