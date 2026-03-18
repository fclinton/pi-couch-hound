import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { UseMutationResult } from "@tanstack/react-query";
import type { AppConfig } from "@/api/types";
import { ApiValidationError } from "@/api/client";
import type { FieldError } from "@/api/client";

interface TextInputProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export function TextInput({ label, value, onChange, placeholder }: TextInputProps) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
    </label>
  );
}

interface NumberInputProps {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
}

export function NumberInput({ label, value, onChange, min, max, step }: NumberInputProps) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        min={min}
        max={max}
        step={step}
        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
    </label>
  );
}

interface SliderInputProps {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
}

export function SliderInput({ label, value, onChange, min, max, step }: SliderInputProps) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-gray-700">
        {label}: <span className="font-normal text-gray-500">{value}</span>
      </span>
      <input
        type="range"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        min={min}
        max={max}
        step={step}
        className="w-full accent-brand-500"
      />
    </label>
  );
}

interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  description?: string;
}

export function Toggle({ label, checked, onChange, description }: ToggleProps) {
  return (
    <label className="flex items-start gap-3">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
      />
      <div>
        <span className="text-sm font-medium text-gray-700">{label}</span>
        {description && (
          <p className="text-xs text-gray-500">{description}</p>
        )}
      </div>
    </label>
  );
}

interface SelectInputProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}

export function SelectInput({ label, value, onChange, options }: SelectInputProps) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function formatFieldLoc(loc: (string | number)[]): string {
  // Pydantic loc is e.g. ["actions", 0, "volume"] — make it human-readable
  const parts: string[] = [];
  for (let i = 0; i < loc.length; i++) {
    const seg = loc[i];
    if (seg === "actions" && typeof loc[i + 1] === "number") {
      parts.push(`Action ${(loc[i + 1] as number) + 1}`);
      i++; // skip the index
    } else if (typeof seg === "string") {
      parts.push(seg.replace(/_/g, " "));
    }
  }
  return parts.join(" \u2192 ") || "Unknown field";
}

function formatFieldErrors(errors: FieldError[]): string[] {
  return errors.map(
    (e) => `${formatFieldLoc(e.loc)}: ${e.msg}`,
  );
}

interface SaveBarProps {
  mutation: UseMutationResult<AppConfig, Error, { section: string; data: unknown }>;
  dirty: boolean;
  onSave: () => void;
  clientErrors?: string[];
}

export function SaveBar({ mutation, dirty, onSave, clientErrors = [] }: SaveBarProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (mutation.isSuccess) {
      timerRef.current = setTimeout(() => mutation.reset(), 2000);
    }
    return () => clearTimeout(timerRef.current);
  }, [mutation.isSuccess, mutation]);

  const serverErrors =
    mutation.isError && mutation.error instanceof ApiValidationError
      ? formatFieldErrors(mutation.error.fieldErrors)
      : mutation.isError
        ? ["Save failed. Please check your values and try again."]
        : [];

  const allErrors = [...clientErrors, ...serverErrors];

  return (
    <div className="space-y-2 border-t border-gray-200 pt-4">
      {allErrors.length > 0 && (
        <div className="rounded-md bg-red-50 p-3">
          <p className="text-sm font-medium text-red-800">
            Please fix the following {allErrors.length === 1 ? "issue" : "issues"}:
          </p>
          <ul className="mt-1 list-inside list-disc space-y-0.5">
            {allErrors.map((msg, i) => (
              <li key={i} className="text-sm text-red-700">
                {msg}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex items-center justify-end gap-3">
        {mutation.isSuccess && (
          <p className="text-sm text-green-600">Saved.</p>
        )}
        <button
          onClick={onSave}
          disabled={mutation.isPending || !dirty}
          className={cn(
            "rounded-md px-4 py-2 text-sm font-medium text-white",
            dirty
              ? "bg-brand-500 hover:bg-brand-600"
              : "cursor-not-allowed bg-gray-300",
          )}
        >
          {mutation.isPending ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}
