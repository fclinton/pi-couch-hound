import { useState, useRef, useEffect, useCallback } from "react";

const TEMPLATE_VARIABLES = [
  { name: "timestamp", description: "ISO 8601 detection time" },
  { name: "confidence", description: "Detection confidence (0-1)" },
  { name: "label", description: "Detected object label" },
  { name: "bbox", description: "Bounding box coordinates" },
  { name: "snapshot_path", description: "Path to snapshot image" },
  { name: "escalation_level", description: "Current escalation level (1-based)" },
  { name: "escalation_elapsed", description: "Seconds since initial detection" },
] as const;

interface TemplateTextareaProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
}

export function TemplateTextarea({
  label,
  value,
  onChange,
  rows = 2,
  placeholder,
}: TemplateTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [triggerPos, setTriggerPos] = useState(0);

  const filtered = TEMPLATE_VARIABLES.filter((v) =>
    v.name.startsWith(filter.toLowerCase()),
  );

  const checkTrigger = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    const cursor = el.selectionStart;
    const textBefore = value.slice(0, cursor);
    const match = textBefore.match(/\{\{(\w*)$/);
    if (match) {
      setOpen(true);
      setFilter(match[1]);
      setTriggerPos(cursor - match[0].length);
      setSelectedIndex(0);
    } else {
      setOpen(false);
    }
  }, [value]);

  const insertVariable = useCallback(
    (varName: string) => {
      const el = textareaRef.current;
      if (!el) return;
      const cursor = el.selectionStart;
      const before = value.slice(0, triggerPos);
      const after = value.slice(cursor);
      const inserted = `{{${varName}}}`;
      const newValue = before + inserted + after;
      onChange(newValue);
      setOpen(false);

      // Restore cursor position after the inserted variable
      const newPos = triggerPos + inserted.length;
      requestAnimationFrame(() => {
        el.focus();
        el.setSelectionRange(newPos, newPos);
      });
    },
    [value, triggerPos, onChange],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!open || filtered.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => (i + 1) % filtered.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => (i - 1 + filtered.length) % filtered.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      insertVariable(filtered[selectedIndex].name);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  };

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={containerRef} className="relative block space-y-1">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
        }}
        onKeyUp={checkTrigger}
        onKeyDown={handleKeyDown}
        onClick={checkTrigger}
        rows={rows}
        placeholder={placeholder}
        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
      {open && filtered.length > 0 && (
        <div className="absolute z-10 mt-1 w-full rounded-md border border-gray-200 bg-white py-1 shadow-lg">
          {filtered.map((v, i) => (
            <button
              key={v.name}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                insertVariable(v.name);
              }}
              className={`flex w-full items-center justify-between px-3 py-1.5 text-left text-sm ${
                i === selectedIndex
                  ? "bg-brand-50 text-brand-700"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              <span className="font-mono">{`{{${v.name}}}`}</span>
              <span className="text-xs text-gray-400">{v.description}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
