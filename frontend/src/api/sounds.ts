import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";

export interface SoundFile {
  filename: string;
  path: string;
  size: number;
}

interface SoundListResponse {
  sounds: SoundFile[];
}

export function useSoundFiles(enabled: boolean = false) {
  return useQuery({
    queryKey: ["sounds"],
    queryFn: () => apiFetch<SoundListResponse>("/sounds"),
    enabled,
    staleTime: 30_000,
    gcTime: 60_000,
    retry: 1,
  });
}
