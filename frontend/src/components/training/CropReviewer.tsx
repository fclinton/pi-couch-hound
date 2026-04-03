import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { useTrainingSamples, useReviewSample } from "@/api/training";
import type { TrainingSample } from "@/api/types";

export default function CropReviewer() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [skippedIds, setSkippedIds] = useState<Set<number>>(new Set());
  const [swipeDir, setSwipeDir] = useState<"left" | "right" | null>(null);

  const { data, isLoading, refetch } = useTrainingSamples({
    source: "crop_capture",
    status: "pending",
    limit: 200,
  });
  const reviewMutation = useReviewSample();

  const pendingSamples: TrainingSample[] =
    data?.samples.filter((s) => !skippedIds.has(s.id)) ?? [];

  const currentSample = pendingSamples[currentIndex] ?? null;
  const totalPending = pendingSamples.length + reviewedCount;
  const isDone = !isLoading && pendingSamples.length === 0;

  const handleReview = useCallback(
    (status: "approved" | "rejected") => {
      if (!currentSample || reviewMutation.isPending) return;

      setSwipeDir(status === "approved" ? "right" : "left");

      reviewMutation.mutate(
        { sampleId: currentSample.id, status },
        {
          onSuccess: () => {
            setReviewedCount((c) => c + 1);
            refetch();
            setTimeout(() => setSwipeDir(null), 150);
          },
          onError: () => {
            setSwipeDir(null);
          },
        },
      );
    },
    [currentSample, reviewMutation, refetch],
  );

  const handleSkip = useCallback(() => {
    if (!currentSample) return;
    setSkippedIds((prev) => new Set(prev).add(currentSample.id));
  }, [currentSample]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowLeft" || e.key === "a") handleReview("rejected");
      else if (e.key === "ArrowRight" || e.key === "d") handleReview("approved");
      else if (e.key === "ArrowDown" || e.key === "s") handleSkip();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleReview, handleSkip]);

  if (isLoading) {
    return <p className="text-sm text-gray-500">Loading pending crops...</p>;
  }

  if (isDone) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="mb-4 text-5xl">&#10003;</div>
        <h3 className="text-lg font-semibold text-gray-900">All caught up!</h3>
        <p className="mt-1 text-sm text-gray-500">
          {reviewedCount > 0
            ? `You reviewed ${reviewedCount} crop${reviewedCount !== 1 ? "s" : ""} this session.`
            : "No pending crop captures to review."}
        </p>
        {skippedIds.size > 0 && (
          <button
            onClick={() => {
              setSkippedIds(new Set());
              setCurrentIndex(0);
            }}
            className="mt-4 rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Review {skippedIds.size} skipped crop{skippedIds.size !== 1 ? "s" : ""}
          </button>
        )}
      </div>
    );
  }

  const imageUrl = currentSample?.image_path
    ? `/api/training/images/${currentSample.image_path.split("/").pop()}`
    : null;

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {reviewedCount} reviewed{skippedIds.size > 0 ? ` / ${skippedIds.size} skipped` : ""}
          </span>
          <span>{pendingSamples.length} remaining</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-gray-200">
          <div
            className="h-full rounded-full bg-brand-500 transition-all duration-300"
            style={{
              width: totalPending > 0 ? `${(reviewedCount / totalPending) * 100}%` : "0%",
            }}
          />
        </div>
      </div>

      {/* Card */}
      {currentSample && (
        <div
          className={cn(
            "mx-auto max-w-lg overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg transition-all duration-150",
            swipeDir === "left" && "-translate-x-4 opacity-70",
            swipeDir === "right" && "translate-x-4 opacity-70",
          )}
        >
          {/* Image */}
          {imageUrl ? (
            <div className="relative">
              <img
                src={imageUrl}
                alt={`Crop ${currentSample.id}`}
                className="w-full"
              />
              {/* Bbox overlay */}
              {currentSample.bbox && currentSample.bbox.length === 4 && (
                <div
                  className="pointer-events-none absolute border-2 border-red-500"
                  style={{
                    left: `${currentSample.bbox[0] * 100}%`,
                    top: `${currentSample.bbox[1] * 100}%`,
                    width: `${(currentSample.bbox[2] - currentSample.bbox[0]) * 100}%`,
                    height: `${(currentSample.bbox[3] - currentSample.bbox[1]) * 100}%`,
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
                  APPROVE
                </span>
              </div>
              <div
                className={cn(
                  "pointer-events-none absolute inset-0 flex items-center justify-center transition-opacity duration-150",
                  swipeDir === "left" ? "bg-red-500/30 opacity-100" : "opacity-0",
                )}
              >
                <span className="rounded-lg bg-red-600 px-4 py-2 text-2xl font-bold text-white">
                  REJECT
                </span>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center bg-gray-100 py-24 text-sm text-gray-400">
              No image
            </div>
          )}

          {/* Sample info */}
          <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3">
            <div className="text-sm text-gray-600">
              <span className="font-medium text-gray-900">#{currentSample.id}</span>{" "}
              <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                {currentSample.label}
              </span>
              <span
                className={cn(
                  "ml-1 inline-block rounded-full px-1.5 py-0.5 text-[10px] font-medium",
                  currentSample.is_positive
                    ? "bg-green-100 text-green-700"
                    : "bg-red-100 text-red-700",
                )}
              >
                {currentSample.is_positive ? "positive" : "negative"}
              </span>
            </div>
            <div className="text-right text-xs text-gray-500">
              {currentSample.confidence != null && (
                <div>{(currentSample.confidence * 100).toFixed(1)}% confidence</div>
              )}
              {currentSample.created_at && (
                <div>{new Date(currentSample.created_at).toLocaleString()}</div>
              )}
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-3 border-t border-gray-100 px-4 py-4">
            <button
              onClick={() => handleReview("rejected")}
              disabled={reviewMutation.isPending}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-red-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-red-700 disabled:opacity-50"
            >
              <span className="text-lg">&larr;</span> Reject
            </button>
            <button
              onClick={handleSkip}
              disabled={reviewMutation.isPending}
              className="rounded-lg border border-gray-300 px-4 py-3 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-50 disabled:opacity-50"
            >
              Skip
            </button>
            <button
              onClick={() => handleReview("approved")}
              disabled={reviewMutation.isPending}
              className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-green-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-green-700 disabled:opacity-50"
            >
              Approve <span className="text-lg">&rarr;</span>
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
        reject &middot;{" "}
        <kbd className="rounded border border-gray-300 px-1.5 py-0.5 font-mono text-gray-600">
          &darr;
        </kbd>{" "}
        skip &middot;{" "}
        <kbd className="rounded border border-gray-300 px-1.5 py-0.5 font-mono text-gray-600">
          &rarr;
        </kbd>{" "}
        approve
      </p>
    </div>
  );
}
