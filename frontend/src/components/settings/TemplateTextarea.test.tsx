import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TemplateTextarea } from "./TemplateTextarea";

function renderTextarea(value = "", onChange = vi.fn()) {
  return { onChange, ...render(
    <TemplateTextarea label="Body" value={value} onChange={onChange} rows={2} />,
  ) };
}

describe("TemplateTextarea", () => {
  it("renders textarea with label and value", () => {
    renderTextarea("hello world");
    expect(screen.getByText("Body")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toHaveValue("hello world");
  });

  it("opens dropdown when {{ is typed", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <TemplateTextarea label="Body" value="" onChange={onChange} rows={2} />,
    );

    // Simulate typing "{{"
    rerender(
      <TemplateTextarea label="Body" value="{{" onChange={onChange} rows={2} />,
    );

    const textarea = screen.getByRole("textbox");
    // Set cursor position to after "{{"
    Object.defineProperty(textarea, "selectionStart", { value: 2, writable: true });
    fireEvent.keyUp(textarea, { key: "{" });

    // Dropdown should show all template variables
    expect(screen.getByText("{{timestamp}}")).toBeInTheDocument();
    expect(screen.getByText("{{confidence}}")).toBeInTheDocument();
    expect(screen.getByText("{{label}}")).toBeInTheDocument();
    expect(screen.getByText("{{bbox}}")).toBeInTheDocument();
    expect(screen.getByText("{{snapshot_path}}")).toBeInTheDocument();
  });

  it("filters variables based on partial input", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <TemplateTextarea label="Body" value="" onChange={onChange} rows={2} />,
    );

    rerender(
      <TemplateTextarea label="Body" value="{{ti" onChange={onChange} rows={2} />,
    );

    const textarea = screen.getByRole("textbox");
    Object.defineProperty(textarea, "selectionStart", { value: 4, writable: true });
    fireEvent.keyUp(textarea, { key: "i" });

    expect(screen.getByText("{{timestamp}}")).toBeInTheDocument();
    expect(screen.queryByText("{{confidence}}")).not.toBeInTheDocument();
  });

  it("inserts variable on click", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <TemplateTextarea label="Body" value="" onChange={onChange} rows={2} />,
    );

    rerender(
      <TemplateTextarea label="Body" value="{{" onChange={onChange} rows={2} />,
    );

    const textarea = screen.getByRole("textbox");
    Object.defineProperty(textarea, "selectionStart", { value: 2, writable: true });
    fireEvent.keyUp(textarea, { key: "{" });

    // Click on "timestamp" option
    fireEvent.mouseDown(screen.getByText("{{timestamp}}"));

    expect(onChange).toHaveBeenCalledWith("{{timestamp}}");
  });

  it("closes dropdown on Escape", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <TemplateTextarea label="Body" value="" onChange={onChange} rows={2} />,
    );

    rerender(
      <TemplateTextarea label="Body" value="{{" onChange={onChange} rows={2} />,
    );

    const textarea = screen.getByRole("textbox");
    Object.defineProperty(textarea, "selectionStart", { value: 2, writable: true });
    fireEvent.keyUp(textarea, { key: "{" });

    expect(screen.getByText("{{timestamp}}")).toBeInTheDocument();

    fireEvent.keyDown(textarea, { key: "Escape" });

    expect(screen.queryByText("{{timestamp}}")).not.toBeInTheDocument();
  });

  it("does not open dropdown for already-closed template expressions", () => {
    const onChange = vi.fn();
    render(
      <TemplateTextarea label="Body" value="{{timestamp}}" onChange={onChange} rows={2} />,
    );

    const textarea = screen.getByRole("textbox");
    // Cursor is after the closing }}
    Object.defineProperty(textarea, "selectionStart", { value: 15, writable: true });
    fireEvent.keyUp(textarea, { key: "}" });

    expect(screen.queryByText("{{confidence}}")).not.toBeInTheDocument();
  });
});
