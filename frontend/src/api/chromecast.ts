import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";

export interface ChromecastDevice {
  friendly_name: string;
  model_name: string | null;
  uuid: string;
}

interface ChromecastDiscoverResponse {
  devices: ChromecastDevice[];
  scan_duration: number;
}

export function useChromecastDiscovery(enabled: boolean = false) {
  return useQuery({
    queryKey: ["chromecast", "discover"],
    queryFn: () => apiFetch<ChromecastDiscoverResponse>("/chromecasts/discover"),
    enabled,
    staleTime: 30_000,
    gcTime: 60_000,
    retry: 1,
  });
}
