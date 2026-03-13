import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { DetectionEvent, EventListResponse, EventStatsResponse } from "./types";

interface EventsQueryParams {
  limit?: number;
  offset?: number;
  since?: string;
  until?: string;
}

export function useEvents(params: EventsQueryParams = {}) {
  const { limit = 20, offset = 0, since, until } = params;
  const searchParams = new URLSearchParams();
  searchParams.set("limit", String(limit));
  searchParams.set("offset", String(offset));
  if (since) searchParams.set("since", since);
  if (until) searchParams.set("until", until);

  return useQuery({
    queryKey: ["events", { limit, offset, since, until }],
    queryFn: () => apiFetch<EventListResponse>(`/events?${searchParams.toString()}`),
  });
}

export function useEventStats() {
  return useQuery({
    queryKey: ["events", "stats"],
    queryFn: () => apiFetch<EventStatsResponse>("/events/stats"),
  });
}

export function useEvent(eventId: number | null) {
  return useQuery({
    queryKey: ["event", eventId],
    queryFn: () => apiFetch<DetectionEvent>(`/events/${eventId}`),
    enabled: eventId != null,
  });
}

export function useDeleteEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (eventId: number) =>
      fetch(`/api/events/${eventId}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });
}

export function useBulkDeleteEvents() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (before: string) =>
      apiFetch<{ deleted: number }>(`/events?before=${encodeURIComponent(before)}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });
}
