import { useState } from "react";
import { useUpdateConfigSection } from "@/api/config";
import type { AppConfig, TwoStageConfig } from "@/api/types";
import { NumberInput, SliderInput, TextInput, Toggle, SaveBar } from "./FormFields";

interface Props {
  config: AppConfig;
}

const defaultTwoStage: TwoStageConfig = {
  enabled: false,
  anchor_label: "couch",
  anchor_confidence: 0.4,
  anchor_padding: 0.1,
  second_stage_confidence: 0.4,
  min_contour_area: 800,
  contour_padding: 0.25,
  debug_overlay: false,
};

export default function DetectionTab({ config }: Props) {
  const d = config.detection;
  const ts = d.two_stage ?? defaultTwoStage;

  const [model, setModel] = useState(d.model);
  const [labels, setLabels] = useState(d.labels);
  const [targetLabel, setTargetLabel] = useState(d.target_label);
  const [confidence, setConfidence] = useState(d.confidence_threshold);
  const [useCoral, setUseCoral] = useState(d.use_coral);

  // Two-stage state
  const [tsEnabled, setTsEnabled] = useState(ts.enabled);
  const [anchorLabel, setAnchorLabel] = useState(ts.anchor_label);
  const [anchorConfidence, setAnchorConfidence] = useState(ts.anchor_confidence);
  const [anchorPadding, setAnchorPadding] = useState(ts.anchor_padding);
  const [secondStageConfidence, setSecondStageConfidence] = useState(ts.second_stage_confidence);
  const [minContourArea, setMinContourArea] = useState(ts.min_contour_area);
  const [contourPadding, setContourPadding] = useState(ts.contour_padding);
  const [debugOverlay, setDebugOverlay] = useState(ts.debug_overlay);

  const mutation = useUpdateConfigSection();

  const dirty =
    model !== d.model ||
    labels !== d.labels ||
    targetLabel !== d.target_label ||
    confidence !== d.confidence_threshold ||
    useCoral !== d.use_coral ||
    tsEnabled !== ts.enabled ||
    anchorLabel !== ts.anchor_label ||
    anchorConfidence !== ts.anchor_confidence ||
    anchorPadding !== ts.anchor_padding ||
    secondStageConfidence !== ts.second_stage_confidence ||
    minContourArea !== ts.min_contour_area ||
    contourPadding !== ts.contour_padding ||
    debugOverlay !== ts.debug_overlay;

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
        two_stage: {
          enabled: tsEnabled,
          anchor_label: anchorLabel,
          anchor_confidence: anchorConfidence,
          anchor_padding: anchorPadding,
          second_stage_confidence: secondStageConfidence,
          min_contour_area: minContourArea,
          contour_padding: contourPadding,
          debug_overlay: debugOverlay,
        },
      },
    });
  };

  return (
    <div className="space-y-6">
      {/* Core detection settings */}
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
      </div>

      {/* Two-stage detection section */}
      <div className="border-t border-gray-200 pt-4">
        <h3 className="mb-3 text-sm font-semibold text-gray-800">Two-Stage Snake Detection</h3>
        <p className="mb-4 text-xs text-gray-500">
          First detect an anchor object (e.g. couch), then use edge contours to find and classify
          objects on it at higher resolution.
        </p>
        <div className="space-y-4">
          <Toggle
            label="Enable two-stage detection"
            checked={tsEnabled}
            onChange={setTsEnabled}
            description="Detect anchor first, then snake contours for per-object inference"
          />

          {tsEnabled && (
            <div className="space-y-4 rounded-md border border-gray-100 bg-gray-50 p-4">
              <TextInput
                label="Anchor label"
                value={anchorLabel}
                onChange={setAnchorLabel}
                placeholder="couch"
              />
              <SliderInput
                label="Anchor confidence"
                value={anchorConfidence}
                onChange={setAnchorConfidence}
                min={0}
                max={1}
                step={0.01}
              />
              <SliderInput
                label="Anchor padding"
                value={anchorPadding}
                onChange={setAnchorPadding}
                min={0}
                max={0.5}
                step={0.01}
              />
              <SliderInput
                label="Second stage confidence"
                value={secondStageConfidence}
                onChange={setSecondStageConfidence}
                min={0}
                max={1}
                step={0.01}
              />
              <NumberInput
                label="Min contour area (px²)"
                value={minContourArea}
                onChange={setMinContourArea}
                min={100}
                max={50000}
                step={100}
              />
              <SliderInput
                label="Contour padding"
                value={contourPadding}
                onChange={setContourPadding}
                min={0}
                max={1}
                step={0.01}
              />
              <Toggle
                label="Debug overlay"
                checked={debugOverlay}
                onChange={setDebugOverlay}
                description="Draw contours, tiles, and anchor box on the live stream"
              />
            </div>
          )}
        </div>
      </div>

      <SaveBar mutation={mutation} dirty={dirty} onSave={handleSave} />
    </div>
  );
}
