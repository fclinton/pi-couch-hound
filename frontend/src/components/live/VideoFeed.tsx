import { useEffect } from "react";
import { useStream } from "@/hooks/useStream";
import { useAppStore } from "@/stores/appStore";

export default function VideoFeed() {
  const { frameUrl, connected } = useStream();
  const setConnected = useAppStore((s) => s.setConnected);

  useEffect(() => {
    setConnected(connected);
  }, [connected, setConnected]);

  return (
    <div className="relative">
      <div className="absolute right-3 top-3 z-10 flex items-center gap-1.5 rounded-full bg-black/50 px-2.5 py-1 text-xs text-white">
        <span
          className={`inline-block h-2 w-2 rounded-full ${connected ? "bg-green-400" : "bg-gray-400"}`}
        />
        {connected ? "Live" : "Disconnected"}
      </div>

      {frameUrl ? (
        <img
          src={frameUrl}
          alt="Live camera feed"
          className="w-full rounded bg-black object-contain"
        />
      ) : (
        <div className="flex h-64 items-center justify-center rounded bg-gray-100 text-sm text-gray-400">
          {connected
            ? "Waiting for frames..."
            : "Camera feed will appear here when connected to a Raspberry Pi"}
        </div>
      )}
    </div>
  );
}
