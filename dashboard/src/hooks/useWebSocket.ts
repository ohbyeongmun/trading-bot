"use client";
import { useEffect, useRef, useCallback, useState } from "react";

interface WSEvent {
  type: string;
  data: any;
  timestamp: string;
}

export function useWebSocket(onEvent?: (event: WSEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const retriesRef = useRef(0);
  const maxRetries = 10;

  const connect = useCallback(() => {
    const apiKey = process.env.NEXT_PUBLIC_API_KEY || "";
    const wsUrl = `ws://localhost:8000/ws/live?key=${apiKey}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        retriesRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "heartbeat") return;
          onEvent?.(data);
        } catch {}
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;

        if (retriesRef.current < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retriesRef.current), 30000);
          retriesRef.current++;
          setTimeout(connect, delay);
        }
      };

      ws.onerror = () => ws.close();
    } catch {}
  }, [onEvent]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected };
}
