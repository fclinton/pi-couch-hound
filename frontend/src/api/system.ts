import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { SystemStatus } from "./types";

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system", "status"],
    queryFn: () => apiFetch<SystemStatus>("/status"),
    refetchInterval: 5000,
  });
}

export function useToggleMonitoring() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ enabled: boolean }>("/monitoring/toggle", { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["system", "status"] });
      queryClient.invalidateQueries({ queryKey: ["config"] });
    },
  });
}
