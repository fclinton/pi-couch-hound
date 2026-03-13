import { useState } from "react";
import { useUpdateConfigSection } from "@/api/config";
import type { AppConfig } from "@/api/types";
import { TextInput, NumberInput, SaveBar } from "./FormFields";
import VideoFeed from "@/components/live/VideoFeed";

interface Props {
  config: AppConfig;
}

export default function CameraTab({ config }: Props) {
  const [source, setSource] = useState(String(config.camera.source));
  const [width, setWidth] = useState(config.camera.resolution[0]);
  const [height, setHeight] = useState(config.camera.resolution[1]);
  const [captureInterval, setCaptureInterval] = useState(config.camera.capture_interval);

  const mutation = useUpdateConfigSection();

  const dirty =
    source !== String(config.camera.source) ||
    width !== config.camera.resolution[0] ||
    height !== config.camera.resolution[1] ||
    captureInterval !== config.camera.capture_interval;

  const handleSave = () => {
    const parsedSource = /^\d+$/.test(source) ? Number(source) : source;
    mutation.mutate({
      section: "camera",
      data: {
        source: parsedSource,
        resolution: [width, height],
        capture_interval: captureInterval,
      },
    });
  };

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded border border-gray-200">
        <VideoFeed />
      </div>
      <TextInput
        label="Source"
        value={source}
        onChange={setSource}
        placeholder="0 or /dev/video0 or rtsp://..."
      />
      <div className="grid grid-cols-2 gap-4">
        <NumberInput label="Width" value={width} onChange={setWidth} min={1} />
        <NumberInput label="Height" value={height} onChange={setHeight} min={1} />
      </div>
      <NumberInput
        label="Capture interval (seconds)"
        value={captureInterval}
        onChange={setCaptureInterval}
        min={0.1}
        max={5.0}
        step={0.1}
      />
      <SaveBar mutation={mutation} dirty={dirty} onSave={handleSave} />
    </div>
  );
}
