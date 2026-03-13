import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface ConfidenceChartProps {
  data: Record<string, number>;
}

export default function ConfidenceChart({ data }: ConfidenceChartProps) {
  const chartData = Object.entries(data)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([range, count]) => ({ label: range, count }));

  if (chartData.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h3 className="mb-4 text-sm font-medium text-gray-700">Confidence Distribution</h3>
        <p className="text-sm text-gray-500">No data available.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h3 className="mb-4 text-sm font-medium text-gray-700">Confidence Distribution</h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="count" fill="var(--color-emerald-500, #10b981)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
