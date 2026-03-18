import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSoundFiles } from "@/api/sounds";

interface SoundFileSelectProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
}

const inputClass =
  "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

export function SoundFileSelect({
  label,
  value,
  onChange,
}: SoundFileSelectProps) {
  const [customMode, setCustomMode] = useState(false);
  const queryClient = useQueryClient();
  const { data, isLoading, isError, isFetching } = useSoundFiles(true);
  const sounds = data?.sounds ?? [];

  const valueInList = sounds.some((s) => s.path === value);
  const showCustom = customMode || (value !== "" && !valueInList && !isLoading);

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["sounds"] });
  };

  if (showCustom && !isLoading) {
    return (
      <label className="block space-y-1">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter file path"
          className={inputClass}
        />
        {sounds.length > 0 && (
          <button
            type="button"
            onClick={() => setCustomMode(false)}
            className="text-xs text-brand-500 hover:text-brand-600"
          >
            Pick from uploaded files
          </button>
        )}
      </label>
    );
  }

  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <div className="flex gap-2">
        <select
          value={value}
          onChange={(e) => {
            if (e.target.value === "__custom__") {
              setCustomMode(true);
              return;
            }
            onChange(e.target.value);
          }}
          disabled={isLoading}
          className={inputClass}
        >
          {isLoading ? (
            <option value="">Loading sounds...</option>
          ) : isError ? (
            <option value="">Failed to load sounds</option>
          ) : sounds.length === 0 ? (
            <option value="">No sound files found</option>
          ) : (
            <>
              <option value="">Select a sound file...</option>
              {sounds.map((s) => (
                <option key={s.path} value={s.path}>
                  {s.filename}
                </option>
              ))}
            </>
          )}
          <option disabled>───</option>
          <option value="__custom__">Enter custom path...</option>
        </select>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={isFetching}
          className="shrink-0 rounded-md border border-gray-300 px-2 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50"
          title="Refresh sound files"
        >
          {isFetching ? "..." : "↻"}
        </button>
      </div>
      {isError && (
        <button
          type="button"
          onClick={() => setCustomMode(true)}
          className="text-xs text-brand-500 hover:text-brand-600"
        >
          Enter path manually
        </button>
      )}
    </label>
  );
}
