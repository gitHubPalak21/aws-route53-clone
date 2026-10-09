"use client";

import Flashbar, { type FlashbarProps } from "@cloudscape-design/components/flashbar";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

interface Notice { id: string; message: string; expiresAt: number }
const NotificationContext = createContext<{ success: (message: string) => void; notices: Notice[]; dismiss: (id: string) => void } | null>(null);

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notices, setNotices] = useState<Notice[]>([]);
  const success = useCallback((message: string) => {
    setNotices((previous) => [...previous.slice(-3), { id: crypto.randomUUID(), message, expiresAt: Date.now() + 30_000 }]);
  }, []);
  const dismiss = useCallback((id: string) => setNotices((previous) => previous.filter((notice) => notice.id !== id)), []);
  useEffect(() => {
    // Only successes expire. Navigation and newer notices do not restart their lifetime.
    const timers = notices.map((notice) => window.setTimeout(() => dismiss(notice.id), Math.max(0, notice.expiresAt - Date.now())));
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [notices, dismiss]);
  const value = useMemo(() => ({ success, notices, dismiss }), [success, notices, dismiss]);
  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

export function useNotifications() {
  const value = useContext(NotificationContext);
  if (!value) throw new Error("Notifications require NotificationProvider");
  return value;
}

export function ConsoleNotifications() {
  const { notices, dismiss } = useNotifications();
  const items: FlashbarProps.MessageDefinition[] = notices.map(({ id, message }) => ({
    id, type: "success", content: message, dismissible: true,
    dismissLabel: "Dismiss notification", onDismiss: () => dismiss(id),
  }));
  return <Flashbar items={items} />;
}
