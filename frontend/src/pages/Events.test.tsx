import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Events from "./Events";

// Mock the events API module
vi.mock("@/api/events", () => ({
  useEvents: vi.fn(),
  useDeleteEvent: vi.fn(),
  useBulkDeleteEvents: vi.fn(),
}));

import { useEvents, useDeleteEvent, useBulkDeleteEvents } from "@/api/events";

const mockUseEvents = vi.mocked(useEvents);
const mockUseDeleteEvent = vi.mocked(useDeleteEvent);
const mockUseBulkDeleteEvents = vi.mocked(useBulkDeleteEvents);

function renderEvents() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Events />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const mockDeleteMutate = vi.fn();
const mockBulkDeleteMutate = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();

  mockUseDeleteEvent.mockReturnValue({
    mutate: mockDeleteMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useDeleteEvent>);

  mockUseBulkDeleteEvents.mockReturnValue({
    mutate: mockBulkDeleteMutate,
    isPending: false,
    isSuccess: false,
    data: undefined,
  } as unknown as ReturnType<typeof useBulkDeleteEvents>);
});

describe("Events page", () => {
  it("renders the heading", () => {
    mockUseEvents.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useEvents>);

    renderEvents();
    expect(
      screen.getByRole("heading", { level: 1, name: "Events" }),
    ).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseEvents.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useEvents>);

    renderEvents();
    expect(screen.getByText("Loading events...")).toBeInTheDocument();
  });

  it("shows error state", () => {
    mockUseEvents.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as unknown as ReturnType<typeof useEvents>);

    renderEvents();
    expect(screen.getByText("Failed to load events.")).toBeInTheDocument();
  });

  it("shows empty state when no events", () => {
    mockUseEvents.mockReturnValue({
      data: { events: [], total: 0, limit: 20, offset: 0 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEvents>);

    renderEvents();
    expect(screen.getByText("No detection events found.")).toBeInTheDocument();
  });

  it("renders event rows with correct data", () => {
    mockUseEvents.mockReturnValue({
      data: {
        events: [
          {
            id: 1,
            timestamp: "2026-03-13T10:00:00Z",
            confidence: 0.92,
            label: "dog",
            bbox: [0.1, 0.2, 0.5, 0.6],
            snapshot_path: "snapshots/snap1.jpg",
            actions_fired: ["play_sound", "take_snapshot"],
          },
          {
            id: 2,
            timestamp: "2026-03-13T11:00:00Z",
            confidence: 0.78,
            label: "dog",
            bbox: [0.2, 0.3, 0.6, 0.7],
            snapshot_path: null,
            actions_fired: [],
          },
        ],
        total: 2,
        limit: 20,
        offset: 0,
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEvents>);

    renderEvents();

    // Check table renders
    const rows = screen.getAllByRole("row");
    // 1 header + 2 data rows
    expect(rows).toHaveLength(3);

    // Check confidence formatting
    expect(screen.getByText("92.0%")).toBeInTheDocument();
    expect(screen.getByText("78.0%")).toBeInTheDocument();

    // Check label badges
    const badges = screen.getAllByText("dog");
    expect(badges).toHaveLength(2);

    // Check actions
    expect(screen.getByText("play_sound, take_snapshot")).toBeInTheDocument();
    expect(screen.getByText("None")).toBeInTheDocument();

    // Check snapshot image
    const img = screen.getByAltText("Detection at 2026-03-13T10:00:00Z");
    expect(img).toHaveAttribute("src", "/api/snapshots/snap1.jpg");

    // Check no-snapshot placeholder
    expect(screen.getByText("No snapshot")).toBeInTheDocument();
  });

  it("shows pagination when more than one page", () => {
    mockUseEvents.mockReturnValue({
      data: {
        events: Array.from({ length: 20 }, (_, i) => ({
          id: i + 1,
          timestamp: `2026-03-13T${String(i).padStart(2, "0")}:00:00Z`,
          confidence: 0.9,
          label: "dog",
          bbox: [0, 0, 1, 1],
          snapshot_path: null,
          actions_fired: [],
        })),
        total: 45,
        limit: 20,
        offset: 0,
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEvents>);

    renderEvents();

    expect(screen.getByText(/Showing 1–20 of 45/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });

  it("does not show pagination for single page", () => {
    mockUseEvents.mockReturnValue({
      data: {
        events: [
          {
            id: 1,
            timestamp: "2026-03-13T10:00:00Z",
            confidence: 0.9,
            label: "dog",
            bbox: [0, 0, 1, 1],
            snapshot_path: null,
            actions_fired: [],
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEvents>);

    renderEvents();
    expect(screen.queryByRole("button", { name: "Previous" })).not.toBeInTheDocument();
  });

  it("calls delete mutation with confirmation", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);

    mockUseEvents.mockReturnValue({
      data: {
        events: [
          {
            id: 42,
            timestamp: "2026-03-13T10:00:00Z",
            confidence: 0.9,
            label: "dog",
            bbox: [0, 0, 1, 1],
            snapshot_path: null,
            actions_fired: [],
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEvents>);

    renderEvents();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(window.confirm).toHaveBeenCalled();
    expect(mockDeleteMutate).toHaveBeenCalledWith(42);
  });

  it("does not delete if user cancels confirmation", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);

    mockUseEvents.mockReturnValue({
      data: {
        events: [
          {
            id: 42,
            timestamp: "2026-03-13T10:00:00Z",
            confidence: 0.9,
            label: "dog",
            bbox: [0, 0, 1, 1],
            snapshot_path: null,
            actions_fired: [],
          },
        ],
        total: 1,
        limit: 20,
        offset: 0,
      },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEvents>);

    renderEvents();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(mockDeleteMutate).not.toHaveBeenCalled();
  });
});
