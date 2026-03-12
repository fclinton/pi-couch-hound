import { useEffect, useRef, useState } from "react";
import { useWebSocket } from "./useWebSocket";

interface UseStreamReturn {
  frameUrl: string | null;
  connected: boolean;
}

const WS_OPTIONS = { binary: true } as const;

export function useStream(): UseStreamReturn {
  const { connected, lastMessage } = useWebSocket("/ws/stream", WS_OPTIONS);
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const prevUrlRef = useRef<string | null>(null);

  useEffect(() => {
    if (!lastMessage) return;

    const blob = new Blob([lastMessage.data], { type: "image/jpeg" });
    const url = URL.createObjectURL(blob);

    if (prevUrlRef.current) {
      URL.revokeObjectURL(prevUrlRef.current);
    }
    prevUrlRef.current = url;
    setFrameUrl(url);
  }, [lastMessage]);

  useEffect(() => {
    return () => {
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
      }
    };
  }, []);

  return { frameUrl, connected };
}
