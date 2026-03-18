import { useState, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLogs } from "@/api/logs";

const LEVEL_COLORS: Record<string, string> = {
  ERROR: "text-red-600",
  WARNING: "text-amber-600",
  DEBUG: "text-blue-500",
  INFO: "text-gray-700",
};

const LEVELS = ["", "DEBUG", "INFO", "WARNING", "ERROR"];

export default function Logs() {
  const [level, setLevel] = useState("");
  const { data, isLoading, isError } = useLogs({
    level: level || undefined,
  });
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [data]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Logs</h1>

      {/* Filters */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex flex-wrap items-end gap-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium text-gray-700">Level</span>
            <select
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              className="block rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="">All</option>
              {LEVELS.filter(Boolean).map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ["logs"] })}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Log display */}
      <div className="rounded-lg border border-gray-200 bg-white">
        {isLoading ? (
          <div className="p-6 text-center text-sm text-gray-500">Loading logs...</div>
        ) : isError ? (
          <div className="p-6 text-center text-sm text-red-600">Failed to load logs.</div>
        ) : !data || data.entries.length === 0 ? (
          <div className="p-6 text-center text-sm text-gray-500">No log entries found.</div>
        ) : (
          <div ref={scrollRef} className="max-h-[70vh] overflow-auto p-4">
            <pre className="text-xs leading-relaxed">
              {data.entries.map((entry, i) => (
                <div key={i} className={LEVEL_COLORS[entry.level] ?? "text-gray-700"}>
                  <span className="text-gray-400">{entry.timestamp}</span>{" "}
                  <span className="font-semibold">{entry.level.padEnd(8)}</span>{" "}
                  <span className="text-gray-500">[{entry.logger}]</span> {entry.message}
                </div>
              ))}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
