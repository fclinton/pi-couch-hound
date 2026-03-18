import { useState, useRef } from "react";
import { cn } from "@/lib/utils";
import {
  useTrainingSamples,
  useTrainingStats,
  useUpdateSample,
  useDeleteSample,
  useCaptureSample,
  useUploadSample,
} from "@/api/training";
import type { TrainingSample } from "@/api/types";

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

  return (
    <div className="group relative overflow-hidden rounded-lg border border-gray-200">
      <img
        src={imageUrl}
        alt={`${sample.label} sample`}
        className="aspect-square w-full object-cover"
        loading="lazy"
      />
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
  const [page, setPage] = useState(0);
  const limit = 12;
  const { data, isLoading } = useTrainingSamples({ limit, offset: page * limit });
  const updateMutation = useUpdateSample();
  const deleteMutation = useDeleteSample();
  const [selected, setSelected] = useState<number | null>(null);

  const selectedSample = data?.samples.find((s) => s.id === selected);

  const handleLabel = (sampleId: number, isPositive: boolean) => {
    updateMutation.mutate({ sampleId, data: { is_positive: isPositive } });
  };

  const handleDelete = (sampleId: number) => {
    if (window.confirm("Delete this training sample?")) {
      deleteMutation.mutate(sampleId);
      if (selected === sampleId) setSelected(null);
    }
  };

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-600">
        Review and label training samples. Mark each image as positive (dog
        present) or negative (false detection / no dog).
      </p>

      {isLoading && (
        <p className="text-sm text-gray-500">Loading samples...</p>
      )}

      {data && data.samples.length === 0 && (
        <p className="py-12 text-center text-sm text-gray-500">
          No samples to label. Add some from the Dataset tab first.
        </p>
      )}

      {data && data.samples.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Image grid */}
          <div className="lg:col-span-2">
            <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
              {data.samples.map((sample) => (
                <button
                  key={sample.id}
                  onClick={() => setSelected(sample.id)}
                  className={cn(
                    "relative overflow-hidden rounded-lg border-2 transition-all",
                    selected === sample.id
                      ? "border-brand-500 ring-2 ring-brand-300"
                      : "border-gray-200 hover:border-gray-300",
                  )}
                >
                  <img
                    src={`/api/training/images/${sample.image_path.split("/").pop()}`}
                    alt={sample.label}
                    className="aspect-square w-full object-cover"
                    loading="lazy"
                  />
                  <span
                    className={cn(
                      "absolute right-1 top-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium",
                      sample.is_positive
                        ? "bg-green-500 text-white"
                        : "bg-red-500 text-white",
                    )}
                  >
                    {sample.is_positive ? "+" : "-"}
                  </span>
                </button>
              ))}
            </div>

            {/* Pagination */}
            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-gray-500">
                {data.total} total samples
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
          </div>

          {/* Detail panel */}
          <div>
            {selectedSample ? (
              <div className="space-y-4 rounded-lg border border-gray-200 p-4">
                <img
                  src={`/api/training/images/${selectedSample.image_path.split("/").pop()}`}
                  alt={selectedSample.label}
                  className="w-full rounded-lg"
                />

                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Label</dt>
                    <dd className="font-medium">{selectedSample.label}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Classification</dt>
                    <dd
                      className={cn(
                        "font-medium",
                        selectedSample.is_positive
                          ? "text-green-600"
                          : "text-red-600",
                      )}
                    >
                      {selectedSample.is_positive ? "Positive" : "Negative"}
                    </dd>
                  </div>
                  {selectedSample.confidence != null && (
                    <div className="flex justify-between">
                      <dt className="text-gray-500">Confidence</dt>
                      <dd className="font-medium">
                        {(selectedSample.confidence * 100).toFixed(1)}%
                      </dd>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Source</dt>
                    <dd className="font-medium">{selectedSample.source}</dd>
                  </div>
                </dl>

                <div className="flex gap-2">
                  <button
                    onClick={() =>
                      handleLabel(selectedSample.id, true)
                    }
                    disabled={updateMutation.isPending}
                    className={cn(
                      "flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      selectedSample.is_positive
                        ? "bg-green-600 text-white"
                        : "border border-green-300 text-green-700 hover:bg-green-50",
                    )}
                  >
                    Positive
                  </button>
                  <button
                    onClick={() =>
                      handleLabel(selectedSample.id, false)
                    }
                    disabled={updateMutation.isPending}
                    className={cn(
                      "flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      !selectedSample.is_positive
                        ? "bg-red-600 text-white"
                        : "border border-red-300 text-red-700 hover:bg-red-50",
                    )}
                  >
                    Negative
                  </button>
                </div>

                <button
                  onClick={() => handleDelete(selectedSample.id)}
                  disabled={deleteMutation.isPending}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  {deleteMutation.isPending ? "Deleting..." : "Delete Sample"}
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-center rounded-lg border border-dashed border-gray-300 p-12">
                <p className="text-sm text-gray-400">
                  Select a sample to label
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
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
