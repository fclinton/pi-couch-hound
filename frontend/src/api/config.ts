import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { AppConfig } from "./types";

export function useConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: () => apiFetch<AppConfig>("/config"),
  });
}

export function useUpdateConfigSection() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ section, data }: { section: string; data: unknown }) =>
      apiFetch<AppConfig>(`/config/${section}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["config"], data);
    },
  });
}
