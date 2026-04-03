import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type {
  TrainingSample,
  TrainingSampleListResponse,
  TrainingStats,
} from "./types";

interface SamplesQueryParams {
  limit?: number;
  offset?: number;
  label?: string;
  is_positive?: boolean;
  source?: string;
  status?: string;
}

export function useTrainingSamples(params: SamplesQueryParams = {}) {
  const { limit = 24, offset = 0, label, is_positive, source, status } = params;
  const searchParams = new URLSearchParams();
  searchParams.set("limit", String(limit));
  searchParams.set("offset", String(offset));
  if (label) searchParams.set("label", label);
  if (is_positive !== undefined) searchParams.set("is_positive", String(is_positive));
  if (source) searchParams.set("source", source);
  if (status) searchParams.set("status", status);

  return useQuery({
    queryKey: ["training", "samples", { limit, offset, label, is_positive, source, status }],
    queryFn: () =>
      apiFetch<TrainingSampleListResponse>(
        `/training/samples?${searchParams.toString()}`,
      ),
  });
}

export function useTrainingSample(sampleId: number | null) {
  return useQuery({
    queryKey: ["training", "sample", sampleId],
    queryFn: () => apiFetch<TrainingSample>(`/training/samples/${sampleId}`),
    enabled: sampleId != null,
  });
}

export function useTrainingStats() {
  return useQuery({
    queryKey: ["training", "stats"],
    queryFn: () => apiFetch<TrainingStats>("/training/stats"),
  });
}

export function useCreateSampleFromEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      eventId,
      is_positive,
      notes,
    }: {
      eventId: number;
      is_positive?: boolean;
      notes?: string;
    }) =>
      apiFetch<TrainingSample>(`/training/samples/from-event/${eventId}`, {
        method: "POST",
        body: JSON.stringify({ is_positive: is_positive ?? true, notes }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training"] });
    },
  });
}

export function useCaptureSample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      label: string;
      is_positive: boolean;
      bbox?: number[];
      notes?: string;
    }) =>
      apiFetch<TrainingSample>("/training/samples/capture", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training"] });
    },
  });
}

export function useUpdateSample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sampleId,
      data,
    }: {
      sampleId: number;
      data: {
        label?: string;
        is_positive?: boolean;
        bbox?: number[];
        notes?: string;
      };
    }) =>
      apiFetch<TrainingSample>(`/training/samples/${sampleId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training"] });
    },
  });
}

export function useDeleteSample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sampleId: number) =>
      apiFetch<{ status: string }>(`/training/samples/${sampleId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training"] });
    },
  });
}

export function useUploadSample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      file,
      label,
      is_positive,
    }: {
      file: File;
      label: string;
      is_positive: boolean;
    }) => {
      const formData = new FormData();
      formData.append("file", file);
      const params = new URLSearchParams();
      params.set("label", label);
      params.set("is_positive", String(is_positive));

      const res = await fetch(
        `/api/training/samples/upload?${params.toString()}`,
        {
          method: "POST",
          body: formData,
        },
      );
      if (!res.ok) {
        throw new Error(`Upload failed: ${res.status}`);
      }
      return res.json() as Promise<TrainingSample>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training"] });
    },
  });
}

export function useReviewSample() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      sampleId,
      status,
    }: {
      sampleId: number;
      status: "approved" | "rejected";
    }) =>
      apiFetch<TrainingSample>(`/training/samples/${sampleId}/review`, {
        method: "POST",
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training"] });
    },
  });
}

export function useReviewBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (items: { id: number; status: "approved" | "rejected" }[]) =>
      apiFetch<{ reviewed: number; errors: string[] }>(
        "/training/samples/review-batch",
        {
          method: "POST",
          body: JSON.stringify({ items }),
        },
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training"] });
    },
  });
}
