import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { UpdateStatus } from "./types";

export function useUpdateStatus() {
  return useQuery({
    queryKey: ["update", "status"],
    queryFn: () => apiFetch<UpdateStatus>("/update/status"),
    refetchInterval: 30000,
  });
}

export function useCheckForUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<UpdateStatus>("/update/check", { method: "POST" }),
    onSuccess: (data) => {
      queryClient.setQueryData(["update", "status"], data);
    },
  });
}

export function useApplyUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<UpdateStatus>("/update/apply", { method: "POST" }),
    onSuccess: (data) => {
      queryClient.setQueryData(["update", "status"], data);
    },
  });
}
