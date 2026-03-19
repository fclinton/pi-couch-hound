import { useState, useRef } from "react";
import { cn } from "@/lib/utils";
import {
  useTrainingSamples,
  useTrainingStats,
  useCaptureSample,
  useUploadSample,
  useDeleteSample,
} from "@/api/training";
import type { TrainingSample } from "@/api/types";
import SwipeLabeler from "@/components/training/SwipeLabeler";

const tabs = ["Dataset", "Labeling", "Export"] as const;
type Tab = (typeof tabs)[number];

export default function Training() {
  const [activeTab, setActiveTab] = useState<Tab>("Dataset");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Model Training</h1>

      <div className="-mx-4 border-b border-gray-200 md:mx-0">
        <nav className="-mb-px flex space-x-4 overflow-x-auto px-4 scrollbar-none sm:space-x-6 md:px-0">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "min-h-[44px] shrink-0 border-b-2 px-1 text-sm font-medium transition-colors",
                activeTab === tab
                  ? "border-brand-500 text-brand-600"
                  : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
              )}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        {activeTab === "Dataset" && <DatasetTab />}
        {activeTab === "Labeling" && <LabelingTab />}
        {activeTab === "Export" && <ExportTab />}
      </div>
    </div>
  );
}

// ── Dataset Tab ──

function DatasetTab() {
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState<"all" | "positive" | "negative">("all");
  const limit = 24;

  const isPositive =
    filter === "positive" ? true : filter === "negative" ? false : undefined;

  const { data, isLoading } = useTrainingSamples({
    limit,
    offset: page * limit,
    is_positive: isPositive,
  });
  const { data: stats } = useTrainingStats();
  const captureMutation = useCaptureSample();
  const uploadMutation = useUploadSample();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleCapture = () => {
    captureMutation.mutate({ label: "dog", is_positive: true });
  };

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadMutation.mutate({ file, label: "dog", is_positive: true });
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Total Samples" value={stats.total} />
          <StatCard
            label="Positive (Dog)"
            value={stats.positive}
            className="text-green-600"
          />
          <StatCard
            label="Negative"
            value={stats.negative}
            className="text-red-600"
          />
          <StatCard
            label="Labels"
            value={Object.keys(stats.by_label).length}
          />
        </div>
      )}

      {/* Actions bar */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleCapture}
          disabled={captureMutation.isPending}
          className="rounded-md bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {captureMutation.isPending ? "Capturing..." : "Capture Frame"}
        </button>

        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadMutation.isPending}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {uploadMutation.isPending ? "Uploading..." : "Upload Image"}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".jpg,.jpeg,.png"
          onChange={handleUpload}
          className="hidden"
        />

        <div className="ml-auto flex gap-1 rounded-md border border-gray-200 p-1">
          {(["all", "positive", "negative"] as const).map((f) => (
            <button
              key={f}
              onClick={() => {
                setFilter(f);
                setPage(0);
              }}
              className={cn(
                "rounded px-3 py-1 text-xs font-medium transition-colors",
                filter === f
                  ? "bg-brand-100 text-brand-700"
                  : "text-gray-500 hover:text-gray-700",
              )}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Sample grid */}
      {isLoading && (
        <p className="text-sm text-gray-500">Loading samples...</p>
      )}

      {data && data.samples.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-sm text-gray-500">
            No training samples yet. Capture frames, upload images, or add
            samples from detection events.
          </p>
        </div>
      )}

      {data && data.samples.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            {data.samples.map((sample) => (
              <SampleCard key={sample.id} sample={sample} />
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-500">
              Showing {page * limit + 1}–
              {Math.min((page + 1) * limit, data.total)} of {data.total}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(Math.max(0, page - 1))}
                disabled={page === 0}
                className="rounded border px-3 py-1 text-sm disabled:opacity-50"
              >
                Prev
              </button>
              <button
                onClick={() => setPage(page + 1)}
                disabled={(page + 1) * limit >= data.total}
                className="rounded border px-3 py-1 text-sm disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  className,
}: {
  label: string;
  value: number;
  className?: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <p className="text-xs font-medium text-gray-500">{label}</p>
      <p className={cn("mt-1 text-2xl font-bold", className ?? "text-gray-900")}>
        {value}
      </p>
    </div>
  );
}

function SampleCard({ sample }: { sample: TrainingSample }) {
  const imageUrl = `/api/training/images/${sample.image_path.split("/").pop()}`;
  const deleteMutation = useDeleteSample();
  const [confirming, setConfirming] = useState(false);

  const handleDelete = () => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    deleteMutation.mutate(sample.id, {
      onSettled: () => setConfirming(false),
    });
  };

  return (
    <div className="group relative overflow-hidden rounded-lg border border-gray-200">
      <img
        src={imageUrl}
        alt={`${sample.label} sample`}
        className="aspect-square w-full object-cover"
        loading="lazy"
      />
      {/* Delete button - visible on hover */}
      <button
        onClick={handleDelete}
        onBlur={() => setConfirming(false)}
        disabled={deleteMutation.isPending}
        className={cn(
          "absolute right-1 top-1 rounded-full p-1 text-xs font-medium shadow transition-opacity",
          confirming
            ? "bg-red-600 text-white opacity-100"
            : "bg-black/50 text-white opacity-0 hover:bg-red-600 group-hover:opacity-100",
          deleteMutation.isPending && "opacity-50",
        )}
        title={confirming ? "Click again to confirm" : "Delete sample"}
      >
        {deleteMutation.isPending ? (
          <span className="inline-block h-4 w-4 text-center">&hellip;</span>
        ) : confirming ? (
          <span className="inline-block px-1">Delete?</span>
        ) : (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="h-4 w-4"
          >
            <path
              fillRule="evenodd"
              d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z"
              clipRule="evenodd"
            />
          </svg>
        )}
      </button>
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-white">{sample.label}</span>
          <span
            className={cn(
              "rounded-full px-1.5 py-0.5 text-[10px] font-medium",
              sample.is_positive
                ? "bg-green-500/80 text-white"
                : "bg-red-500/80 text-white",
            )}
          >
            {sample.is_positive ? "+" : "-"}
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Labeling Tab ──

function LabelingTab() {
  return <SwipeLabeler />;
}

// ── Export Tab ──

function ExportTab() {
  const { data: stats } = useTrainingStats();
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch("/api/training/export");
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Export failed" }));
        alert(err.detail || "Export failed");
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "training_dataset.zip";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
        <h3 className="text-sm font-semibold text-blue-800">
          Export Training Dataset
        </h3>
        <p className="mt-1 text-sm text-blue-700">
          Export your labeled training data as a ZIP file containing images and
          Pascal VOC format annotations. You can use this dataset to train a
          custom TFLite model on a more powerful machine, then upload the
          resulting model via Settings.
        </p>
      </div>

      {stats && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-700">
            Dataset Summary
          </h3>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <StatCard label="Total Samples" value={stats.total} />
            <StatCard
              label="Positive"
              value={stats.positive}
              className="text-green-600"
            />
            <StatCard
              label="Negative"
              value={stats.negative}
              className="text-red-600"
            />
          </div>

          {Object.keys(stats.by_label).length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-medium text-gray-500">
                By Label
              </h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(stats.by_label).map(([label, count]) => (
                  <span
                    key={label}
                    className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700"
                  >
                    {label}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}

          {Object.keys(stats.by_source).length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-medium text-gray-500">
                By Source
              </h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(stats.by_source).map(([source, count]) => (
                  <span
                    key={source}
                    className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700"
                  >
                    {source}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
        <h3 className="text-sm font-semibold text-gray-700">
          Export Contents
        </h3>
        <ul className="mt-2 space-y-1 text-sm text-gray-600">
          <li>
            <code className="rounded bg-gray-200 px-1 text-xs">images/</code> —
            All training images (JPEG/PNG)
          </li>
          <li>
            <code className="rounded bg-gray-200 px-1 text-xs">
              annotations/
            </code>{" "}
            — Pascal VOC XML annotations with bounding boxes
          </li>
          <li>
            <code className="rounded bg-gray-200 px-1 text-xs">
              manifest.json
            </code>{" "}
            — Full dataset metadata
          </li>
        </ul>
      </div>

      <button
        onClick={handleExport}
        disabled={exporting || !stats || stats.total === 0}
        className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
      >
        {exporting ? "Exporting..." : "Download Dataset ZIP"}
      </button>
    </div>
  );
}
