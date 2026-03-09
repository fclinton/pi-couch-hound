import { useSystemStatus } from "@/api/system";

export default function Dashboard() {
  const { data: status, isLoading } = useSystemStatus();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>

      <div className="grid gap-4 md:grid-cols-3">
        <StatusCard
          label="Status"
          value={isLoading ? "Loading..." : (status?.status ?? "Unknown")}
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

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-800">
          Live Camera Feed
        </h2>
        <div className="flex h-64 items-center justify-center rounded bg-gray-100 text-sm text-gray-400">
          Camera feed will appear here when connected to a Raspberry Pi
        </div>
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
