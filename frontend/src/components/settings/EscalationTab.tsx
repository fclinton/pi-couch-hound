import { useState } from "react";
import { useUpdateConfigSection } from "@/api/config";
import type { AppConfig, EscalationConfig, EscalationLevelConfig } from "@/api/types";
import { NumberInput, Toggle, SaveBar } from "./FormFields";

interface Props {
  config: AppConfig;
}

const MAX_LEVELS = 5;

function newLevel(): EscalationLevelConfig {
  return { delay: 0, actions: [] };
}

export default function EscalationTab({ config }: Props) {
  const [escalation, setEscalation] = useState<EscalationConfig>(config.escalation);
  const mutation = useUpdateConfigSection();

  const dirty = JSON.stringify(escalation) !== JSON.stringify(config.escalation);

  const handleSave = () => {
    mutation.mutate({ section: "escalation", data: escalation });
  };

  const update = (patch: Partial<EscalationConfig>) => {
    setEscalation({ ...escalation, ...patch });
  };

  const updateLevel = (index: number, patch: Partial<EscalationLevelConfig>) => {
    const next = [...escalation.levels];
    next[index] = { ...next[index], ...patch };
    update({ levels: next });
  };

  const addLevel = () => {
    if (escalation.levels.length >= MAX_LEVELS) return;
    update({ levels: [...escalation.levels, newLevel()] });
  };

  const removeLevel = (index: number) => {
    update({ levels: escalation.levels.filter((_, i) => i !== index) });
  };

  const toggleAction = (levelIndex: number, actionName: string) => {
    const level = escalation.levels[levelIndex];
    const actions = level.actions.includes(actionName)
      ? level.actions.filter((n) => n !== actionName)
      : [...level.actions, actionName];
    updateLevel(levelIndex, { actions });
  };

  const actionNames = config.actions.filter((a) => a.enabled).map((a) => a.name);

  return (
    <div className="space-y-4">
      <Toggle
        label="Enable escalation"
        checked={escalation.enabled}
        onChange={(v) => update({ enabled: v })}
        description="When enabled, actions fire in escalation levels instead of all at once."
      />

      {escalation.enabled && (
        <>
          <NumberInput
            label="Reset cooldown (seconds)"
            value={escalation.reset_cooldown}
            onChange={(v) => update({ reset_cooldown: v })}
            min={0}
          />
          <p className="text-xs text-gray-500">
            Seconds with no detection before resetting to level 1. Use 0 for immediate reset.
          </p>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-700">
                Escalation levels ({escalation.levels.length}/{MAX_LEVELS})
              </p>
              <button
                onClick={addLevel}
                disabled={escalation.levels.length >= MAX_LEVELS}
                className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                Add level
              </button>
            </div>

            {escalation.levels.map((level, i) => (
              <div
                key={i}
                className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">
                    Level {i + 1}
                  </span>
                  <button
                    onClick={() => removeLevel(i)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                </div>

                <NumberInput
                  label="Delay (seconds after initial detection)"
                  value={level.delay}
                  onChange={(v) => updateLevel(i, { delay: v })}
                  min={0}
                />

                <div className="space-y-1">
                  <span className="text-sm font-medium text-gray-700">Actions</span>
                  {actionNames.length === 0 && (
                    <p className="text-xs text-gray-400">
                      No enabled actions configured. Add actions in the Actions tab first.
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    {actionNames.map((name) => (
                      <button
                        key={name}
                        type="button"
                        onClick={() => toggleAction(i, name)}
                        className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                          level.actions.includes(name)
                            ? "bg-brand-100 text-brand-700 ring-1 ring-brand-300"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                        }`}
                      >
                        {name}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      <SaveBar mutation={mutation} dirty={dirty} onSave={handleSave} />
    </div>
  );
}
