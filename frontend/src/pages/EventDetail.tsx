import { useParams, useNavigate } from "react-router-dom";
import { useEvent, useDeleteEvent } from "@/api/events";

export default function EventDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const eventId = id ? Number(id) : null;
  const { data: event, isLoading, isError } = useEvent(eventId);
  const deleteMutation = useDeleteEvent();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-sm text-gray-500">
        Loading event...
      </div>
    );
  }

  if (isError || !event) {
    return (
      <div className="space-y-4 py-20 text-center">
        <p className="text-sm text-red-600">Event not found.</p>
        <button
          onClick={() => navigate("/events")}
          className="text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          Back to Events
        </button>
      </div>
    );
  }

  const handleDelete = () => {
    if (window.confirm("Delete this event and its snapshot?")) {
      deleteMutation.mutate(event.id, {
        onSuccess: () => navigate("/events"),
      });
    }
  };

  const snapshotUrl = event.snapshot_path
    ? `/api/snapshots/${event.snapshot_path.split("/").pop()}`
    : null;

  // bbox is normalized [x1, y1, x2, y2] in 0..1
  const [bx1, by1, bx2, by2] = event.bbox;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/events")}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            &larr; Back
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Event #{event.id}</h1>
        </div>
        <button
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          {deleteMutation.isPending ? "Deleting..." : "Delete Event"}
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Snapshot with bounding box overlay */}
        <div className="lg:col-span-2">
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <h2 className="border-b border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700">
              Snapshot
            </h2>
            {snapshotUrl ? (
              <div className="relative">
                <img
                  src={snapshotUrl}
                  alt={`Detection event ${event.id}`}
                  className="block w-full"
                />
                {/* Bounding box overlay */}
                <div
                  data-testid="bbox-overlay"
                  className="pointer-events-none absolute border-2 border-red-500"
                  style={{
                    left: `${bx1 * 100}%`,
                    top: `${by1 * 100}%`,
                    width: `${(bx2 - bx1) * 100}%`,
                    height: `${(by2 - by1) * 100}%`,
                  }}
                >
                  <span className="absolute -top-5 left-0 rounded bg-red-500 px-1 text-xs font-medium text-white">
                    {event.label} {(event.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center py-24 text-sm text-gray-400">
                No snapshot available
              </div>
            )}
          </div>
        </div>

        {/* Metadata & actions sidebar */}
        <div className="space-y-6">
          {/* Metadata */}
          <div className="rounded-lg border border-gray-200 bg-white">
            <h2 className="border-b border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700">
              Metadata
            </h2>
            <dl className="divide-y divide-gray-100 px-4">
              <div className="flex justify-between py-3">
                <dt className="text-sm text-gray-500">ID</dt>
                <dd className="text-sm font-medium text-gray-900">{event.id}</dd>
              </div>
              <div className="flex justify-between py-3">
                <dt className="text-sm text-gray-500">Timestamp</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {new Date(event.timestamp).toLocaleString()}
                </dd>
              </div>
              <div className="flex justify-between py-3">
                <dt className="text-sm text-gray-500">Label</dt>
                <dd>
                  <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                    {event.label}
                  </span>
                </dd>
              </div>
              <div className="flex justify-between py-3">
                <dt className="text-sm text-gray-500">Confidence</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {(event.confidence * 100).toFixed(1)}%
                </dd>
              </div>
              <div className="flex justify-between py-3">
                <dt className="text-sm text-gray-500">Bounding Box</dt>
                <dd className="text-sm font-mono text-gray-900">
                  [{event.bbox.map((v) => v.toFixed(2)).join(", ")}]
                </dd>
              </div>
            </dl>
          </div>

          {/* Actions fired */}
          <div className="rounded-lg border border-gray-200 bg-white">
            <h2 className="border-b border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700">
              Actions Fired
            </h2>
            <div className="px-4 py-3">
              {event.actions_fired.length > 0 ? (
                <ul className="space-y-2">
                  {event.actions_fired.map((action) => (
                    <li
                      key={action}
                      className="flex items-center gap-2 text-sm text-gray-900"
                    >
                      <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
                      {action}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-400">No actions were fired.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
