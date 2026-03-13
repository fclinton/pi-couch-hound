import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import EventStats from "./EventStats";

// ResizeObserver is not available in jsdom, but recharts needs it
beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

vi.mock("@/api/events", () => ({
  useEventStats: vi.fn(),
}));

import { useEventStats } from "@/api/events";

const mockUseEventStats = vi.mocked(useEventStats);

function renderEventStats() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <EventStats />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("EventStats page", () => {
  it("renders the heading", () => {
    mockUseEventStats.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useEventStats>);

    renderEventStats();
    expect(screen.getByRole("heading", { level: 1, name: "Statistics" })).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseEventStats.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useEventStats>);

    renderEventStats();
    expect(screen.getByText("Loading statistics...")).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseEventStats.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof useEventStats>);

    renderEventStats();
    expect(screen.getByText("Failed to load statistics.")).toBeInTheDocument();
  });

  it("renders summary cards with stats data", () => {
    mockUseEventStats.mockReturnValue({
      data: {
        total_events: 142,
        avg_confidence: 0.876,
        detections_per_hour: { "2026-03-13T10": 5, "2026-03-13T11": 8 },
        detections_per_day: { "2026-03-12": 20, "2026-03-13": 15 },
        peak_hour: 14,
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEventStats>);

    renderEventStats();

    expect(screen.getByText("142")).toBeInTheDocument();
    expect(screen.getByText("87.6%")).toBeInTheDocument();
    expect(screen.getByText("2:00 PM - 3:00 PM")).toBeInTheDocument();
  });

  it("shows N/A when peak_hour is null", () => {
    mockUseEventStats.mockReturnValue({
      data: {
        total_events: 0,
        avg_confidence: 0,
        detections_per_hour: {},
        detections_per_day: {},
        peak_hour: null,
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEventStats>);

    renderEventStats();

    expect(screen.getByText("N/A")).toBeInTheDocument();
  });

  it("renders chart section titles", () => {
    mockUseEventStats.mockReturnValue({
      data: {
        total_events: 10,
        avg_confidence: 0.9,
        detections_per_hour: { "2026-03-13T10": 3 },
        detections_per_day: { "2026-03-13": 5 },
        peak_hour: 10,
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEventStats>);

    renderEventStats();

    expect(screen.getByText("Detections Per Hour (Last 24h)")).toBeInTheDocument();
    expect(screen.getByText("Detections Per Day (Last 7 Days)")).toBeInTheDocument();
  });
});
