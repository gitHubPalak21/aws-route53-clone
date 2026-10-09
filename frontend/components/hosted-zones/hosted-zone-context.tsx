"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

const ResourceContext = createContext<{
  resource: { id: string; name: string } | null;
  setResource: (resource: { id: string; name: string }) => void;
} | null>(null);

export function HostedZoneContextProvider({ children }: { children: ReactNode }) {
  const [resource, setResource] = useState<{ id: string; name: string } | null>(null);
  const value = useMemo(() => ({ resource, setResource }), [resource]);
  return <ResourceContext.Provider value={value}>{children}</ResourceContext.Provider>;
}

export function useHostedZoneContext() {
  const value = useContext(ResourceContext);
  if (!value) throw new Error("Hosted zone context requires HostedZoneContextProvider");
  return value;
}
