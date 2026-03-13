import { useState } from "react";
import { useUpdateConfigSection } from "@/api/config";
import type { AppConfig } from "@/api/types";
import { useStream } from "@/hooks/useStream";
import { SliderInput, Toggle, SaveBar } from "./FormFields";
import PolygonEditor from "./PolygonEditor";

interface Props {
  config: AppConfig;
}

export default function RoiTab({ config }: Props) {
  const roi = config.detection.roi;
  const { frameUrl } = useStream();
  const [enabled, setEnabled] = useState(roi.enabled);
  const [minOverlap, setMinOverlap] = useState(roi.min_overlap);
  const [polygon, setPolygon] = useState<number[][]>(roi.polygon);

  const mutation = useUpdateConfigSection();

  const polygonDirty = JSON.stringify(polygon) !== JSON.stringify(roi.polygon);
  const dirty = enabled !== roi.enabled || minOverlap !== roi.min_overlap || polygonDirty;

  const handleSave = () => {
    mutation.mutate({
      section: "detection",
      data: {
        roi: {
          enabled,
          polygon,
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
        <PolygonEditor
          polygon={polygon}
          onChange={setPolygon}
          resolution={config.camera.resolution}
          backgroundUrl={frameUrl}
        />
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPolygon([])}
            className="rounded-md border border-gray-300 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50"
          >
            Clear
          </button>
          <span className="text-xs text-gray-400">
            Click to add points. Drag to move. Right-click a point to remove it.
          </span>
        </div>
      </div>
      <SaveBar mutation={mutation} dirty={dirty} onSave={handleSave} />
    </div>
  );
}
