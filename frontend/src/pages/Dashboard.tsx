import { useSystemStatus } from "@/api/system";
import { useWebSocket } from "@/hooks/useWebSocket";
import VideoFeed from "@/components/live/VideoFeed";

interface WsStatus {
  cpu_percent: number;
  memory_percent: number;
  temperature: number | null;
  pipeline_state: string;
  detection_count: number;
  last_detection_time: string | null;
}

export default function Dashboard() {
  const { data: status, isLoading } = useSystemStatus();
  const { lastMessage: wsStatusMsg, connected: wsConnected } = useWebSocket("/ws/status");

  const wsStatus: WsStatus | null = wsStatusMsg
    ? (JSON.parse(wsStatusMsg.data as string) as WsStatus)
    : null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      <div className="grid gap-4 md:grid-cols-3">
        <StatusCard
          label="Status"
          value={
            wsConnected
              ? (wsStatus?.pipeline_state ?? "Connected")
              : isLoading
                ? "Loading..."
                : (status?.status ?? "Unknown")
          }
        />
        <StatusCard
          label="Uptime"
          value={
            status
              ? `${Math.floor(status.uptime_seconds / 60)}m`
              : "--"
          }
        />
        <StatusCard label="Version" value={status?.version ?? "--"} />
      </div>

      {wsConnected && wsStatus && (
        <div className="grid gap-4 md:grid-cols-4">
          <StatusCard
            label="CPU"
            value={`${wsStatus.cpu_percent}%`}
          />
          <StatusCard
            label="Memory"
            value={`${wsStatus.memory_percent}%`}
          />
          <StatusCard
            label="Temperature"
            value={wsStatus.temperature != null ? `${wsStatus.temperature}°C` : "N/A"}
          />
          <StatusCard
            label="Detections"
            value={String(wsStatus.detection_count)}
          />
        </div>
      )}

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-800">
          Live Camera Feed
        </h2>
        <VideoFeed />
      </div>
    </div>
  );
}

function StatusCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="text-xs font-medium uppercase text-gray-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-gray-900">{value}</p>
    </div>
  );
}
