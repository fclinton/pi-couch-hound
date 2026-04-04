import { useEffect, useMemo } from "react";
import { useWebSocket } from "./useWebSocket";

interface UseStreamReturn {
  frameUrl: string | null;
  connected: boolean;
}

const WS_OPTIONS = { binary: true } as const;

export function useStream(): UseStreamReturn {
  const { connected, lastMessage } = useWebSocket("/ws/stream", WS_OPTIONS);

  const frameUrl = useMemo(() => {
    if (!lastMessage) return null;

    const blob = new Blob([lastMessage.data], { type: "image/jpeg" });
    return URL.createObjectURL(blob);
  }, [lastMessage]);

  useEffect(() => {
    return () => {
      if (frameUrl) {
        URL.revokeObjectURL(frameUrl);
      }
    };
  }, [frameUrl]);

  return { frameUrl, connected };
}
