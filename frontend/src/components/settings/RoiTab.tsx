import { useState } from "react";
import { useUpdateConfigSection } from "@/api/config";
import type { AppConfig } from "@/api/types";
import { SliderInput, Toggle, SaveBar } from "./FormFields";

interface Props {
  config: AppConfig;
}

export default function RoiTab({ config }: Props) {
  const roi = config.detection.roi;
  const [enabled, setEnabled] = useState(roi.enabled);
  const [minOverlap, setMinOverlap] = useState(roi.min_overlap);

  const mutation = useUpdateConfigSection();

  const dirty = enabled !== roi.enabled || minOverlap !== roi.min_overlap;

  const handleSave = () => {
    mutation.mutate({
      section: "detection",
      data: {
        roi: {
          enabled,
          polygon: roi.polygon,
          min_overlap: minOverlap,
        },
      },
    });
  };

  return (
    <div className="space-y-4">
      <Toggle
        label="Enable ROI filtering"
        checked={enabled}
        onChange={setEnabled}
        description="Only trigger actions when detections overlap with the defined region."
      />
      <SliderInput
        label="Min overlap"
        value={minOverlap}
        onChange={setMinOverlap}
        min={0}
        max={1}
        step={0.01}
      />
      <div className="space-y-1">
        <span className="text-sm font-medium text-gray-700">Polygon</span>
        <pre className="rounded-md bg-gray-50 p-3 text-xs text-gray-600">
          {JSON.stringify(roi.polygon, null, 2)}
        </pre>
        <p className="text-xs text-gray-400">
          Polygon drawing tool coming soon. Edit the config file directly to change vertices.
        </p>
      </div>
      <SaveBar mutation={mutation} dirty={dirty} onSave={handleSave} />
    </div>
  );
}
