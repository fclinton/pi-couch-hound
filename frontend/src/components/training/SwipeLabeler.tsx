import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { useCreateSampleFromEvent } from "@/api/training";
import { useEvents } from "@/api/events";
import type { DetectionEvent } from "@/api/types";

export default function SwipeLabeler() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [labeledCount, setLabeledCount] = useState(0);
  const [skippedIds, setSkippedIds] = useState<Set<number>>(new Set());
  const [swipeDir, setSwipeDir] = useState<"left" | "right" | null>(null);

  const { data, isLoading, refetch } = useEvents({ limit: 200 });
  const addToTraining = useCreateSampleFromEvent();

  const untrainedEvents: DetectionEvent[] =
    data?.events.filter(
      (e) => e.training === null && e.snapshot_path !== null && !skippedIds.has(e.id),
    ) ?? [];

  const currentEvent = untrainedEvents[currentIndex] ?? null;
  const totalUntrained = untrainedEvents.length + labeledCount;
  const isDone = !isLoading && untrainedEvents.length === 0;

  const handleLabel = useCallback(
    (isPositive: boolean) => {
      if (!currentEvent || addToTraining.isPending) return;

      setSwipeDir(isPositive ? "right" : "left");

      addToTraining.mutate(
        { eventId: currentEvent.id, is_positive: isPositive },
        {
          onSuccess: () => {
            setLabeledCount((c) => c + 1);
            refetch();
            setTimeout(() => setSwipeDir(null), 150);
          },
          onError: () => {
            setSwipeDir(null);
          },
        },
      );
    },
    [currentEvent, addToTraining, refetch],
  );

  const handleSkip = useCallback(() => {
    if (!currentEvent) return;
    setSkippedIds((prev) => new Set(prev).add(currentEvent.id));
  }, [currentEvent]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowLeft" || e.key === "a") handleLabel(false);
      else if (e.key === "ArrowRight" || e.key === "d") handleLabel(true);
      else if (e.key === "ArrowDown" || e.key === "s") handleSkip();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleLabel, handleSkip]);

  if (isLoading) {
    return <p className="text-sm text-gray-500">Loading events...</p>;
  }

  if (isDone) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="mb-4 text-5xl">&#10003;</div>
        <h3 className="text-lg font-semibold text-gray-900">All caught up!</h3>
        <p className="mt-1 text-sm text-gray-500">
          {labeledCount > 0
            ? `You labeled ${labeledCount} event${labeledCount !== 1 ? "s" : ""} this session.`
            : "No untrained events with snapshots to label."}
        </p>
        {skippedIds.size > 0 && (
          <button
            onClick={() => {
              setSkippedIds(new Set());
              setCurrentIndex(0);
            }}
            className="mt-4 rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Review {skippedIds.size} skipped event{skippedIds.size !== 1 ? "s" : ""}
          </button>
        )}
      </div>
    );
  }

  const snapshotUrl = currentEvent?.snapshot_path
    ? `/api/snapshots/${currentEvent.snapshot_path.split("/").pop()}`
    : null;

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {labeledCount} labeled{skippedIds.size > 0 ? ` / ${skippedIds.size} skipped` : ""}
          </span>
          <span>{untrainedEvents.length} remaining</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-gray-200">
          <div
            className="h-full rounded-full bg-brand-500 transition-all duration-300"
            style={{
              width: totalUntrained > 0 ? `${(labeledCount / totalUntrained) * 100}%` : "0%",
            }}
          />
        </div>
      </div>

      {/* Card */}
      {currentEvent && (
        <div
          className={cn(
            "mx-auto max-w-lg overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg transition-all duration-150",
            swipeDir === "left" && "-translate-x-4 opacity-70",
            swipeDir === "right" && "translate-x-4 opacity-70",
          )}
        >
          {/* Snapshot */}
          {snapshotUrl ? (
            <div className="relative">
              <img
                src={snapshotUrl}
                alt={`Event ${currentEvent.id}`}
                className="w-full"
              />
              {/* Bbox overlay */}
              {currentEvent.bbox.length === 4 && (
                <div
                  className="pointer-events-none absolute border-2 border-red-500"
                  style={{
                    left: `${currentEvent.bbox[0] * 100}%`,
                    top: `${currentEvent.bbox[1] * 100}%`,
                    width: `${(currentEvent.bbox[2] - currentEvent.bbox[0]) * 100}%`,
                    height: `${(currentEvent.bbox[3] - currentEvent.bbox[1]) * 100}%`,
                  }}
                />
              )}
              {/* Swipe indicator overlays */}
              <div
                className={cn(
                  "pointer-events-none absolute inset-0 flex items-center justify-center transition-opacity duration-150",
                  swipeDir === "right" ? "bg-green-500/30 opacity-100" : "opacity-0",
                )}
              >
                <span className="rounded-lg bg-green-600 px-4 py-2 text-2xl font-bold text-white">
                  DOG
                </span>
              </div>
              <div
                className={cn(
                  "pointer-events-none absolute inset-0 flex items-center justify-center transition-opacity duration-150",
                  swipeDir === "left" ? "bg-red-500/30 opacity-100" : "opacity-0",
                )}
              >
                <span className="rounded-lg bg-red-600 px-4 py-2 text-2xl font-bold text-white">
                  NOPE
                </span>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center bg-gray-100 py-24 text-sm text-gray-400">
              No snapshot
            </div>
          )}

          {/* Event info */}
          <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3">
            <div className="text-sm text-gray-600">
              <span className="font-medium text-gray-900">#{currentEvent.id}</span>{" "}
              <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                {currentEvent.label}
              </span>
            </div>
            <div className="text-right text-xs text-gray-500">
              <div>{(currentEvent.confidence * 100).toFixed(1)}% confidence</div>
              <div>{new Date(currentEvent.timestamp).toLocaleString()}</div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-3 border-t border-gray-100 px-4 py-4">
            <button
              onClick={() => handleLabel(false)}
              disabled={addToTraining.isPending}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-red-700 disabled:opacity-50"
            >
              <span className="text-lg">&larr;</span> Not a Dog
            </button>
            <button
              onClick={handleSkip}
              disabled={addToTraining.isPending}
              className="rounded-lg border border-gray-300 px-4 py-3 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-50 disabled:opacity-50"
            >
              Skip
            </button>
            <button
              onClick={() => handleLabel(true)}
              disabled={addToTraining.isPending}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-green-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-green-700 disabled:opacity-50"
            >
              Dog <span className="text-lg">&rarr;</span>
            </button>
          </div>
        </div>
      )}

      {/* Keyboard hint */}
      <p className="text-center text-xs text-gray-400">
        Keyboard:{" "}
        <kbd className="rounded border border-gray-300 px-1.5 py-0.5 font-mono text-gray-600">
          &larr;
        </kbd>{" "}
        negative &middot;{" "}
        <kbd className="rounded border border-gray-300 px-1.5 py-0.5 font-mono text-gray-600">
          &darr;
        </kbd>{" "}
        skip &middot;{" "}
        <kbd className="rounded border border-gray-300 px-1.5 py-0.5 font-mono text-gray-600">
          &rarr;
        </kbd>{" "}
        positive
      </p>
    </div>
  );
}
