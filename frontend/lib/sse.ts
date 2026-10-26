"use client";

import { useEffect, useState } from "react";
import { apiBaseUrl } from "./api";
import { AlertSchema, type Alert } from "./schemas";

export function useAlertStream(onAlert: (alert: Alert) => void): boolean {
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    const stream = new EventSource(`${apiBaseUrl}/alerts/stream`, { withCredentials: true });
    const handle = (event: Event) => {
      try {
        const parsed = JSON.parse((event as MessageEvent<string>).data) as unknown;
        const payload = AlertSchema.safeParse(
          typeof parsed === "object" && parsed !== null && "alert" in parsed
            ? (parsed as { alert: unknown }).alert
            : parsed,
        );
        if (payload.success) onAlert(payload.data);
      } catch { /* Ignore malformed event data and wait for the next valid event. */ }
    };
    const onOpen = () => setConnected(true);
    const onError = () => setConnected(false);
    stream.addEventListener("alert.created", handle);
    stream.addEventListener("alert.updated", handle);
    stream.addEventListener("open", onOpen);
    stream.addEventListener("error", onError);
    return () => stream.close();
  }, [onAlert]);
  return connected;
}
