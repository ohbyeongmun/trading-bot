"use client";
import { useEffect, useRef, useState, useCallback } from "react";

interface WSEvent {
  type: string;
  data: any;
  timestamp: string;
}

export function useWebSocket(onEvent?: (event: WSEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const retriesRef = useRef(0);
  const onEventRef = useRef(onEvent);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);

  // onEvent를 ref로 저장해서 connect의 의존성에서 제거
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const connect = useCallback(() => {
    // 이미 연결 중이면 스킵
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
    // 연결 중인 소켓이 있으면 닫기
    if (wsRef.current) {
      try { wsRef.current.close(); } catch {}
      wsRef.current = null;
    }

    const apiKey = process.env.NEXT_PUBLIC_API_KEY || "";
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const wsBase = baseUrl.replace(/^http/, "ws");
    const wsUrl = `${wsBase}/ws/live?key=${apiKey}`;

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
          // heartbeat에 pong 응답
          if (data.type === "heartbeat") {
            ws.send("ping");
            return;
          }
          onEventRef.current?.(data);
        } catch {}
      };

      ws.onclose = (e) => {
        setConnected(false);
        wsRef.current = null;

        // 무한 재연결 (최대 간격 30초)
        const delay = Math.min(2000 * Math.pow(1.5, Math.min(retriesRef.current, 10)), 30000);
        retriesRef.current++;
        reconnectTimerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        // onerror 후 onclose가 자동 호출됨 — 여기서는 아무것도 안 함
      };
    } catch {
      // 연결 실패 시에도 재시도
      const delay = Math.min(2000 * Math.pow(1.5, Math.min(retriesRef.current, 10)), 30000);
      retriesRef.current++;
      reconnectTimerRef.current = setTimeout(connect, delay);
    }
  }, []); // 의존성 없음 — onEvent는 ref로 접근

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        try { wsRef.current.close(); } catch {}
      }
    };
  }, [connect]);

  return { connected };
}
