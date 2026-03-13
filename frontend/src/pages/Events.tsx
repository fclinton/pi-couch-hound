import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useEvents, useDeleteEvent, useBulkDeleteEvents } from "@/api/events";

const PAGE_SIZE = 20;

export default function Events() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  const { data, isLoading, isError } = useEvents({
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    since: since || undefined,
    until: until || undefined,
  });

  const deleteMutation = useDeleteEvent();
  const bulkDeleteMutation = useBulkDeleteEvents();

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  const handleDelete = useCallback(
    (id: number) => {
      if (window.confirm("Delete this event and its snapshot?")) {
        deleteMutation.mutate(id);
      }
    },
    [deleteMutation],
  );

  const handleBulkDelete = useCallback(() => {
    if (!until) return;
    if (
      window.confirm(
        `Delete all events before ${new Date(until).toLocaleString()}? This cannot be undone.`,
      )
    ) {
      bulkDeleteMutation.mutate(until, {
        onSuccess: () => setPage(0),
      });
    }
  }, [until, bulkDeleteMutation]);

  const clearFilters = useCallback(() => {
    setSince("");
    setUntil("");
    setPage(0);
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Events</h1>

      {/* Filters */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex flex-wrap items-end gap-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium text-gray-700">Since</span>
            <input
              type="datetime-local"
              value={since ? toLocalDateTimeValue(since) : ""}
              onChange={(e) => {
                setSince(e.target.value ? new Date(e.target.value).toISOString() : "");
                setPage(0);
              }}
              className="block rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium text-gray-700">Until</span>
            <input
              type="datetime-local"
              value={until ? toLocalDateTimeValue(until) : ""}
              onChange={(e) => {
                setUntil(e.target.value ? new Date(e.target.value).toISOString() : "");
                setPage(0);
              }}
              className="block rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </label>
          <button
            onClick={clearFilters}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Clear Filters
          </button>
          {until && (
            <button
              onClick={handleBulkDelete}
              disabled={bulkDeleteMutation.isPending}
              className="rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {bulkDeleteMutation.isPending ? "Deleting..." : "Bulk Delete Before Until"}
            </button>
          )}
        </div>
        {bulkDeleteMutation.isSuccess && (
          <p className="mt-2 text-sm text-green-600">
            Deleted {bulkDeleteMutation.data.deleted} events.
          </p>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        {isLoading ? (
          <div className="p-6 text-center text-sm text-gray-500">Loading events...</div>
        ) : isError ? (
          <div className="p-6 text-center text-sm text-red-600">Failed to load events.</div>
        ) : !data || data.events.length === 0 ? (
          <div className="p-6 text-center text-sm text-gray-500">
            No detection events found.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Snapshot
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Timestamp
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Label
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Confidence
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Actions Fired
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium uppercase text-gray-500">
                  Delete
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {data.events.map((event) => (
                <tr
                  key={event.id}
                  onClick={() => navigate(`/events/${event.id}`)}
                  className="cursor-pointer hover:bg-gray-50"
                >
                  <td className="px-4 py-3">
                    {event.snapshot_path ? (
                      <img
                        src={`/api/snapshots/${event.snapshot_path.split("/").pop()}`}
                        alt={`Detection at ${event.timestamp}`}
                        className="h-12 w-16 rounded object-cover"
                      />
                    ) : (
                      <span className="text-xs text-gray-400">No snapshot</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    {new Date(event.timestamp).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                      {event.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    {(event.confidence * 100).toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {event.actions_fired.length > 0
                      ? event.actions_fired.join(", ")
                      : "None"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(event.id);
                      }}
                      disabled={deleteMutation.isPending}
                      className="text-sm text-red-600 hover:text-red-800 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Showing {page * PAGE_SIZE + 1}–
            {Math.min((page + 1) * PAGE_SIZE, data?.total ?? 0)} of {data?.total ?? 0}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded-md border border-gray-300 px-3 py-1 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="rounded-md border border-gray-300 px-3 py-1 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Convert an ISO string to the `YYYY-MM-DDTHH:mm` format expected by datetime-local inputs. */
function toLocalDateTimeValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
