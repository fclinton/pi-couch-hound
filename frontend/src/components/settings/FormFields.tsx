import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { UseMutationResult } from "@tanstack/react-query";
import type { AppConfig } from "@/api/types";

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

interface SaveBarProps {
  mutation: UseMutationResult<AppConfig, Error, { section: string; data: unknown }>;
  dirty: boolean;
  onSave: () => void;
}

export function SaveBar({ mutation, dirty, onSave }: SaveBarProps) {
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (mutation.isSuccess) {
      timerRef.current = setTimeout(() => mutation.reset(), 2000);
    }
    return () => clearTimeout(timerRef.current);
  }, [mutation.isSuccess, mutation]);

  return (
    <div className="flex items-center justify-end gap-3 border-t border-gray-200 pt-4">
      {mutation.isError && (
        <p className="text-sm text-red-600">Save failed. Check values.</p>
      )}
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
  );
}
