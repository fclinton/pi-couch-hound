import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { LogsResponse } from "./types";

interface LogsQueryParams {
  lines?: number;
  level?: string;
}

export function useLogs(params: LogsQueryParams = {}) {
  const { lines = 200, level } = params;
  const searchParams = new URLSearchParams();
  searchParams.set("lines", String(lines));
  if (level) searchParams.set("level", level);

  return useQuery({
    queryKey: ["logs", { lines, level }],
    queryFn: () => apiFetch<LogsResponse>(`/logs?${searchParams.toString()}`),
  });
}
