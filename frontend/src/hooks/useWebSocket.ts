import { useEffect, useRef, useState, useCallback } from "react";
import { getToken } from "@/stores/authStore";

interface UseWebSocketOptions {
  binary?: boolean;
}

interface UseWebSocketReturn {
  connected: boolean;
  lastMessage: MessageEvent | null;
}

const RECONNECT_CAP_MS = 30_000;

function buildWsUrl(path: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  // Browsers can't set an Authorization header on a WebSocket handshake, so the
  // JWT is passed as a query parameter (the server reads it the same way).
  const token = getToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${protocol}//${window.location.host}${path}${query}`;
}

export function useWebSocket(
  path: string,
  options?: UseWebSocketOptions,
): UseWebSocketReturn {
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelay = useRef(1000);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmounted = useRef(false);
  const connectRef = useRef<(() => void) | null>(null);

  const connect = useCallback(() => {
    if (unmounted.current) return;

    const ws = new WebSocket(buildWsUrl(path));
    if (options?.binary) {
      ws.binaryType = "arraybuffer";
    }
    wsRef.current = ws;

    ws.onopen = () => {
      // Ignore events from a socket that has since been replaced (e.g. a
      // StrictMode remount or a path change created a newer connection).
      if (unmounted.current || wsRef.current !== ws) {
        ws.close();
        return;
      }
      setConnected(true);
      reconnectDelay.current = 1000;
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!unmounted.current && wsRef.current === ws) {
        setLastMessage(event);
      }
    };

    ws.onclose = () => {
      if (unmounted.current || wsRef.current !== ws) return;
      setConnected(false);
      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(
          reconnectDelay.current * 2,
          RECONNECT_CAP_MS,
        );
        connectRef.current?.();
      }, reconnectDelay.current);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [path, options?.binary]);

  useEffect(() => {
    connectRef.current = connect;
  });

  useEffect(() => {
    unmounted.current = false;
    connect();

    return () => {
      unmounted.current = true;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected, lastMessage };
}
