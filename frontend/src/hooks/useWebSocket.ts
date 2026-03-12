import { useEffect, useRef, useState, useCallback } from "react";

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
  return `${protocol}//${window.location.host}${path}`;
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

  const connect = useCallback(() => {
    if (unmounted.current) return;

    const ws = new WebSocket(buildWsUrl(path));
    if (options?.binary) {
      ws.binaryType = "arraybuffer";
    }
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmounted.current) {
        ws.close();
        return;
      }
      setConnected(true);
      reconnectDelay.current = 1000;
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!unmounted.current) {
        setLastMessage(event);
      }
    };

    ws.onclose = () => {
      if (unmounted.current) return;
      setConnected(false);
      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(
          reconnectDelay.current * 2,
          RECONNECT_CAP_MS,
        );
        connect();
      }, reconnectDelay.current);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [path, options?.binary]);

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
