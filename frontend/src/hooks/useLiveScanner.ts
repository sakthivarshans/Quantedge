import { useEffect, useRef, useState } from "react";
import type { Opportunity } from "../api/client";

function resolveWsUrl(): string {
  const apiUrl = import.meta.env.VITE_API_URL as string | undefined;

  if (apiUrl) {
    // apiUrl looks like "https://quantedge-backend.up.railway.app/api" --
    // strip the /api suffix and swap http(s) for ws(s), keeping the backend's own host.
    // This is the path used when frontend and backend are on separate domains/services
    // (e.g. Railway, Render as two services) rather than sharing one nginx origin.
    const base = apiUrl.replace(/\/api\/?$/, "");
    const wsBase = base.replace(/^http/, "ws");
    return `${wsBase}/ws/live-scanner`;
  }

  // Same-origin fallback: Docker Compose / nginx setups where /ws is proxied to the
  // backend from the same domain the frontend is served from (see nginx.conf).
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws/live-scanner`;
}

export function useLiveScanner(enabled: boolean) {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) {
      wsRef.current?.close();
      setConnected(false);
      return;
    }

    const url = resolveWsUrl();
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "scanner_update") {
          setOpportunities(msg.data.opportunities);
          setLastUpdate(new Date());
        }
      } catch {
        // ignore malformed frames
      }
    };

    return () => ws.close();
  }, [enabled]);

  return { opportunities, connected, lastUpdate };
}
