import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useEvents } from "@/api/events";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { DetectionEvent } from "@/api/types";

function snapshotUrl(path: string): string {
  const filename = path.split("/").pop() ?? path;
  return `/api/snapshots/${filename}`;
}

function EventCard({ event }: { event: DetectionEvent }) {
  return (
    <div className="w-40 flex-shrink-0 snap-start rounded-lg border border-gray-200 bg-white overflow-hidden">
      <div className="h-24 bg-gray-100">
        {event.snapshot_path ? (
          <img
            src={snapshotUrl(event.snapshot_path)}
            alt={`Detection at ${event.timestamp}`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-gray-400">
            No snapshot
          </div>
        )}
      </div>
      <div className="p-2">
        <p className="text-xs font-medium text-gray-900">
          {(event.confidence * 100).toFixed(1)}%
        </p>
        <p className="text-xs text-gray-500">
          {new Date(event.timestamp).toLocaleTimeString()}
        </p>
      </div>
    </div>
  );
}

export default function EventsTicker() {
  const { data, isLoading } = useEvents({ limit: 20 });
  const { lastMessage } = useWebSocket("/ws/events");
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<DetectionEvent[]>([]);

  // Sync from REST query
  useEffect(() => {
    if (data?.events) {
      setEvents(data.events);
    }
  }, [data]);

  // On WebSocket event, invalidate the events query to refetch with full data
  useEffect(() => {
    if (lastMessage) {
      queryClient.invalidateQueries({ queryKey: ["events"] });
    }
  }, [lastMessage, queryClient]);

  if (isLoading) {
    return <p className="text-sm text-gray-400">Loading recent events...</p>;
  }

  if (events.length === 0) {
    return <p className="text-sm text-gray-400">No recent detections</p>;
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-2 snap-x snap-mandatory">
      {events.map((event) => (
        <EventCard key={event.id} event={event} />
      ))}
    </div>
  );
}
