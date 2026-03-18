import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useChromecastDiscovery } from "@/api/chromecast";

interface ChromecastDeviceSelectProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
}

const inputClass =
  "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500";

export function ChromecastDeviceSelect({
  label,
  value,
  onChange,
}: ChromecastDeviceSelectProps) {
  const [customMode, setCustomMode] = useState(false);
  const queryClient = useQueryClient();
  const { data, isLoading, isError, isFetching } = useChromecastDiscovery(true);
  const devices = data?.devices ?? [];

  // If value is set but not in the discovered list, show custom mode
  const valueInList = devices.some((d) => d.friendly_name === value);
  const showCustom = customMode || (value !== "" && !valueInList && !isLoading);

  const handleRescan = () => {
    queryClient.invalidateQueries({ queryKey: ["chromecast", "discover"] });
  };

  if (showCustom && !isLoading) {
    return (
      <label className="block space-y-1">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter device name"
          className={inputClass}
        />
        {devices.length > 0 && (
          <button
            type="button"
            onClick={() => setCustomMode(false)}
            className="text-xs text-brand-500 hover:text-brand-600"
          >
            Pick from discovered devices
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
            <option value="">Scanning network...</option>
          ) : isError ? (
            <option value="">Discovery failed</option>
          ) : devices.length === 0 ? (
            <option value="">No devices found</option>
          ) : (
            <>
              <option value="">Select a device...</option>
              {devices.map((d) => (
                <option key={d.uuid} value={d.friendly_name}>
                  {d.friendly_name}
                  {d.model_name ? ` (${d.model_name})` : ""}
                </option>
              ))}
            </>
          )}
          <option disabled>───</option>
          <option value="__custom__">Enter custom name...</option>
        </select>
        <button
          type="button"
          onClick={handleRescan}
          disabled={isFetching}
          className="shrink-0 rounded-md border border-gray-300 px-2 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50"
          title="Rescan network"
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
          Enter name manually
        </button>
      )}
    </label>
  );
}
