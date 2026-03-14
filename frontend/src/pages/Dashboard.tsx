import { useSystemStatus, useToggleMonitoring } from "@/api/system";
import { useWebSocket } from "@/hooks/useWebSocket";
import VideoFeed from "@/components/live/VideoFeed";
import EventsTicker from "@/components/dashboard/EventsTicker";

interface WsStatus {
  cpu_percent: number;
  memory_percent: number;
  temperature: number | null;
  pipeline_state: string;
  monitoring_enabled: boolean;
  detection_count: number;
  last_detection_time: string | null;
}

export default function Dashboard() {
  const { data: status, isLoading } = useSystemStatus();
  const { lastMessage: wsStatusMsg, connected: wsConnected } = useWebSocket("/ws/status");
  const toggleMonitoring = useToggleMonitoring();

  const wsStatus: WsStatus | null = wsStatusMsg
    ? (JSON.parse(wsStatusMsg.data as string) as WsStatus)
    : null;

  const monitoringEnabled = wsConnected
    ? (wsStatus?.monitoring_enabled ?? true)
    : (status?.monitoring_enabled ?? true);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      <div
        className={`flex items-center justify-between rounded-lg border p-4 ${
          monitoringEnabled
            ? "border-brand-200 bg-brand-50"
            : "border-gray-300 bg-gray-100"
        }`}
      >
        <div>
          <p className="text-sm font-semibold text-gray-900">
            {monitoringEnabled ? "Monitoring Active" : "Monitoring Paused"}
          </p>
          <p className="text-xs text-gray-500">
            {monitoringEnabled
              ? "Actions will fire on detection"
              : "Detection continues but actions are suppressed"}
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={monitoringEnabled}
          disabled={toggleMonitoring.isPending}
          onClick={() => toggleMonitoring.mutate()}
          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${
            monitoringEnabled ? "bg-brand-500" : "bg-gray-300"
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform ${
              monitoringEnabled ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
      </div>

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
          Recent Detections
        </h2>
        <EventsTicker />
      </div>

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
