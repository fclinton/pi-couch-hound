import { useState } from "react";
import { useUpdateConfigSection } from "@/api/config";
import type { AppConfig } from "@/api/types";
import { TextInput, SliderInput, Toggle, SaveBar } from "./FormFields";

interface Props {
  config: AppConfig;
}

export default function DetectionTab({ config }: Props) {
  const d = config.detection;
  const [model, setModel] = useState(d.model);
  const [labels, setLabels] = useState(d.labels);
  const [targetLabel, setTargetLabel] = useState(d.target_label);
  const [confidence, setConfidence] = useState(d.confidence_threshold);
  const [useCoral, setUseCoral] = useState(d.use_coral);

  const mutation = useUpdateConfigSection();

  const dirty =
    model !== d.model ||
    labels !== d.labels ||
    targetLabel !== d.target_label ||
    confidence !== d.confidence_threshold ||
    useCoral !== d.use_coral;

  const handleSave = () => {
    mutation.mutate({
      section: "detection",
      data: {
        model,
        labels,
        target_label: targetLabel,
        confidence_threshold: confidence,
        use_coral: useCoral,
        roi: config.detection.roi,
      },
    });
  };

  return (
    <div className="space-y-4">
      <TextInput label="Model path" value={model} onChange={setModel} />
      <TextInput label="Labels path" value={labels} onChange={setLabels} />
      <TextInput label="Target label" value={targetLabel} onChange={setTargetLabel} />
      <SliderInput
        label="Confidence threshold"
        value={confidence}
        onChange={setConfidence}
        min={0}
        max={1}
        step={0.01}
      />
      <Toggle label="Use Coral TPU" checked={useCoral} onChange={setUseCoral} />
      <SaveBar mutation={mutation} dirty={dirty} onSave={handleSave} />
    </div>
  );
}
