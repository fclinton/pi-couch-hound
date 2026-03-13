import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ActionsTab from "./ActionsTab";
import type { AppConfig } from "@/api/types";

vi.mock("@/api/config", () => ({
  useUpdateConfigSection: vi.fn(),
}));

import { useUpdateConfigSection } from "@/api/config";

const mockUseUpdateConfigSection = vi.mocked(useUpdateConfigSection);

const mockMutate = vi.fn();

function makeConfig(actions: AppConfig["actions"]): AppConfig {
  return { actions } as unknown as AppConfig;
}

function renderActionsTab(actions: AppConfig["actions"]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ActionsTab config={makeConfig(actions)} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseUpdateConfigSection.mockReturnValue({
    mutate: mockMutate,
    isPending: false,
    isError: false,
    isSuccess: false,
    reset: vi.fn(),
  } as unknown as ReturnType<typeof useUpdateConfigSection>);
});

describe("ActionsTab reorder", () => {
  const threeActions = [
    { name: "Alert", type: "sound" as const, enabled: true },
    { name: "Snap", type: "snapshot" as const, enabled: true },
    { name: "Notify", type: "http" as const, enabled: true },
  ];

  it("disables up button on first action and down button on last", () => {
    renderActionsTab(threeActions);

    const upButtons = screen.getAllByLabelText(/Move .* up/);
    const downButtons = screen.getAllByLabelText(/Move .* down/);

    expect(upButtons[0]).toBeDisabled();
    expect(downButtons[downButtons.length - 1]).toBeDisabled();

    // Middle action should have both enabled
    expect(upButtons[1]).toBeEnabled();
    expect(downButtons[1]).toBeEnabled();
  });

  it("moves first action down when clicking its down button", () => {
    renderActionsTab(threeActions);

    const downButtons = screen.getAllByLabelText(/Move .* down/);
    fireEvent.click(downButtons[0]);

    // After moving Alert down, Snap should be first
    const names = screen.getAllByText(/(Alert|Snap|Notify)/);
    expect(names[0]).toHaveTextContent("Snap");
    expect(names[1]).toHaveTextContent("Alert");
    expect(names[2]).toHaveTextContent("Notify");
  });

  it("moves last action up when clicking its up button", () => {
    renderActionsTab(threeActions);

    const upButtons = screen.getAllByLabelText(/Move .* up/);
    fireEvent.click(upButtons[2]);

    const names = screen.getAllByText(/(Alert|Snap|Notify)/);
    expect(names[0]).toHaveTextContent("Alert");
    expect(names[1]).toHaveTextContent("Notify");
    expect(names[2]).toHaveTextContent("Snap");
  });

  it("enables save button after reordering", () => {
    renderActionsTab(threeActions);

    // Save button should initially be disabled (not dirty)
    const saveButton = screen.getByRole("button", { name: "Save" });
    expect(saveButton).toBeDisabled();

    // Move first action down
    const downButtons = screen.getAllByLabelText(/Move .* down/);
    fireEvent.click(downButtons[0]);

    // Save should now be enabled (dirty)
    expect(saveButton).toBeEnabled();
  });
});
