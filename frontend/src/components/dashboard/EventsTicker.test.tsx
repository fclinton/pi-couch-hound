import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import EventsTicker from "./EventsTicker";

vi.mock("@/api/events", () => ({
  useEvents: vi.fn(),
}));

vi.mock("@/hooks/useWebSocket", () => ({
  useWebSocket: vi.fn(),
}));

import { useEvents } from "@/api/events";
import { useWebSocket } from "@/hooks/useWebSocket";

const mockUseEvents = vi.mocked(useEvents);
const mockUseWebSocket = vi.mocked(useWebSocket);

function renderTicker() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <EventsTicker />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseWebSocket.mockReturnValue({ connected: false, lastMessage: null });
});

describe("EventsTicker", () => {
  it("shows loading state", () => {
    mockUseEvents.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as unknown as ReturnType<typeof useEvents>);

    renderTicker();
    expect(screen.getByText("Loading recent events...")).toBeInTheDocument();
  });

  it("shows empty state when no events", () => {
    mockUseEvents.mockReturnValue({
      data: { events: [], total: 0, limit: 20, offset: 0 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useEvents>);

    renderTicker();
    expect(screen.getByText("No recent detections")).toBeInTheDocument();
  });

  it("renders event cards with thumbnails and data", () => {
    mockUseEvents.mockReturnValue({
      data: {
        events: [
          {
            id: 1,
            timestamp: "2026-03-13T10:30:00Z",
            confidence: 0.92,
            label: "dog",
            bbox: [0.1, 0.2, 0.5, 0.6],
            snapshot_path: "snapshots/snap1.jpg",
            actions_fired: [],
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

    renderTicker();

    // Check confidence values
    expect(screen.getByText("92.0%")).toBeInTheDocument();
    expect(screen.getByText("78.0%")).toBeInTheDocument();

    // Check snapshot image
    const img = screen.getByAltText("Detection at 2026-03-13T10:30:00Z");
    expect(img).toHaveAttribute("src", "/api/snapshots/snap1.jpg");

    // Check no-snapshot placeholder
    expect(screen.getByText("No snapshot")).toBeInTheDocument();
  });
});
