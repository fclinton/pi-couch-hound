import { useEventStats } from "@/api/events";
import DetectionChart from "@/components/stats/DetectionChart";

function formatHourLabel(key: string): string {
  // key format: "YYYY-MM-DDTHH"
  const hour = parseInt(key.slice(-2), 10);
  const suffix = hour >= 12 ? "PM" : "AM";
  const h = hour % 12 || 12;
  return `${h}${suffix}`;
}

function formatDayLabel(key: string): string {
  // key format: "YYYY-MM-DD"
  const date = new Date(key + "T00:00:00");
  return date.toLocaleDateString(undefined, { weekday: "short", month: "numeric", day: "numeric" });
}

function formatPeakHour(hour: number): string {
  const suffix = hour >= 12 ? "PM" : "AM";
  const h = hour % 12 || 12;
  const nextHour = (hour + 1) % 24;
  const nextSuffix = nextHour >= 12 ? "PM" : "AM";
  const nh = nextHour % 12 || 12;
  return `${h}:00 ${suffix} - ${nh}:00 ${nextSuffix}`;
}

export default function EventStats() {
  const { data, isLoading, isError } = useEventStats();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Statistics</h1>
        <p className="text-sm text-gray-500">Loading statistics...</p>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Statistics</h1>
        <p className="text-sm text-red-600">Failed to load statistics.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Statistics</h1>

      {/* Summary cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium uppercase text-gray-500">Total Events</p>
          <p className="mt-1 text-xl font-semibold text-gray-900">{data.total_events}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium uppercase text-gray-500">Avg Confidence</p>
          <p className="mt-1 text-xl font-semibold text-gray-900">
            {(data.avg_confidence * 100).toFixed(1)}%
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs font-medium uppercase text-gray-500">Peak Hour</p>
          <p className="mt-1 text-xl font-semibold text-gray-900">
            {data.peak_hour != null ? formatPeakHour(data.peak_hour) : "N/A"}
          </p>
        </div>
      </div>

      {/* Charts */}
      <DetectionChart
        data={data.detections_per_hour}
        title="Detections Per Hour (Last 24h)"
        formatLabel={formatHourLabel}
      />
      <DetectionChart
        data={data.detections_per_day}
        title="Detections Per Day (Last 7 Days)"
        formatLabel={formatDayLabel}
      />
    </div>
  );
}
