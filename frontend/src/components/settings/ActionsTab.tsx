import { useState } from "react";
import { useUpdateConfigSection } from "@/api/config";
import type { ActionConfig, ActionType, AppConfig } from "@/api/types";
import { cn } from "@/lib/utils";
import { TextInput, NumberInput, SelectInput, Toggle, SaveBar } from "./FormFields";

interface Props {
  config: AppConfig;
}

const ACTION_TYPES: { value: ActionType; label: string }[] = [
  { value: "sound", label: "Sound" },
  { value: "snapshot", label: "Snapshot" },
  { value: "http", label: "HTTP" },
  { value: "mqtt", label: "MQTT" },
  { value: "script", label: "Script" },
  { value: "gpio", label: "GPIO" },
];

function newAction(type: ActionType): ActionConfig {
  return { name: "", type, enabled: true };
}

const TYPE_COLORS: Record<ActionType, string> = {
  sound: "bg-purple-100 text-purple-700",
  snapshot: "bg-blue-100 text-blue-700",
  http: "bg-green-100 text-green-700",
  mqtt: "bg-yellow-100 text-yellow-800",
  script: "bg-gray-100 text-gray-700",
  gpio: "bg-red-100 text-red-700",
};

function ActionFields({
  action,
  onChange,
}: {
  action: ActionConfig;
  onChange: (a: ActionConfig) => void;
}) {
  const set = <K extends keyof ActionConfig>(key: K, val: ActionConfig[K]) =>
    onChange({ ...action, [key]: val });

  return (
    <div className="space-y-3 pt-3">
      <div className="grid grid-cols-2 gap-4">
        <TextInput label="Name" value={action.name} onChange={(v) => set("name", v)} />
        <SelectInput
          label="Type"
          value={action.type}
          onChange={(v) => set("type", v as ActionType)}
          options={ACTION_TYPES}
        />
      </div>

      {action.type === "sound" && (
        <div className="grid grid-cols-2 gap-4">
          <TextInput
            label="Sound file"
            value={action.sound_file ?? ""}
            onChange={(v) => set("sound_file", v || null)}
          />
          <NumberInput
            label="Volume (0–100)"
            value={action.volume ?? 80}
            onChange={(v) => set("volume", v)}
            min={0}
            max={100}
          />
        </div>
      )}

      {action.type === "snapshot" && (
        <div className="grid grid-cols-2 gap-4">
          <TextInput
            label="Save directory"
            value={action.save_dir ?? ""}
            onChange={(v) => set("save_dir", v || null)}
          />
          <NumberInput
            label="Max kept"
            value={action.max_kept ?? 100}
            onChange={(v) => set("max_kept", v)}
            min={1}
          />
        </div>
      )}

      {action.type === "http" && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <TextInput
              label="URL"
              value={action.url ?? ""}
              onChange={(v) => set("url", v || null)}
            />
            <SelectInput
              label="Method"
              value={action.method ?? "POST"}
              onChange={(v) => set("method", v)}
              options={[
                { value: "GET", label: "GET" },
                { value: "POST", label: "POST" },
                { value: "PUT", label: "PUT" },
              ]}
            />
          </div>
          <label className="block space-y-1">
            <span className="text-sm font-medium text-gray-700">Headers (JSON)</span>
            <textarea
              value={action.headers ? JSON.stringify(action.headers) : ""}
              onChange={(e) => {
                try {
                  set("headers", e.target.value ? JSON.parse(e.target.value) : null);
                } catch {
                  // allow invalid JSON while typing
                }
              }}
              rows={2}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium text-gray-700">Body</span>
            <textarea
              value={action.body ?? ""}
              onChange={(e) => set("body", e.target.value || null)}
              rows={2}
              className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </label>
        </>
      )}

      {action.type === "mqtt" && (
        <>
          <div className="grid grid-cols-2 gap-4">
            <TextInput
              label="Broker"
              value={action.broker ?? ""}
              onChange={(v) => set("broker", v || null)}
            />
            <NumberInput
              label="Port"
              value={action.port ?? 1883}
              onChange={(v) => set("port", v)}
              min={1}
              max={65535}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <TextInput
              label="Topic"
              value={action.topic ?? ""}
              onChange={(v) => set("topic", v || null)}
            />
            <TextInput
              label="Payload"
              value={action.payload ?? ""}
              onChange={(v) => set("payload", v || null)}
            />
          </div>
        </>
      )}

      {action.type === "script" && (
        <div className="grid grid-cols-2 gap-4">
          <TextInput
            label="Command"
            value={action.command ?? ""}
            onChange={(v) => set("command", v || null)}
          />
          <NumberInput
            label="Timeout (s)"
            value={action.timeout ?? 30}
            onChange={(v) => set("timeout", v)}
            min={1}
          />
        </div>
      )}

      {action.type === "gpio" && (
        <div className="grid grid-cols-3 gap-4">
          <NumberInput
            label="Pin"
            value={action.pin ?? 0}
            onChange={(v) => set("pin", v)}
            min={0}
          />
          <SelectInput
            label="Mode"
            value={action.mode ?? "pulse"}
            onChange={(v) => set("mode", v as "pulse" | "toggle" | "momentary")}
            options={[
              { value: "pulse", label: "Pulse" },
              { value: "toggle", label: "Toggle" },
              { value: "momentary", label: "Momentary" },
            ]}
          />
          <NumberInput
            label="Duration (s)"
            value={action.duration ?? 1}
            onChange={(v) => set("duration", v)}
            min={0}
            step={0.1}
          />
        </div>
      )}
    </div>
  );
}

export default function ActionsTab({ config }: Props) {
  const [actions, setActions] = useState<ActionConfig[]>(config.actions);
  const [expanded, setExpanded] = useState<number | null>(null);

  const mutation = useUpdateConfigSection();

  const dirty = JSON.stringify(actions) !== JSON.stringify(config.actions);

  const handleSave = () => {
    mutation.mutate({ section: "actions", data: actions });
  };

  const updateAction = (index: number, action: ActionConfig) => {
    const next = [...actions];
    next[index] = action;
    setActions(next);
  };

  const removeAction = (index: number) => {
    setActions(actions.filter((_, i) => i !== index));
    setExpanded(null);
  };

  const addAction = () => {
    setActions([...actions, newAction("sound")]);
    setExpanded(actions.length);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">{actions.length} action(s) configured</p>
        <button
          onClick={addAction}
          className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600"
        >
          Add action
        </button>
      </div>

      {actions.map((action, i) => (
        <div
          key={i}
          className="rounded-lg border border-gray-200 bg-gray-50 p-4"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setExpanded(expanded === i ? null : i)}
                className="text-sm font-medium text-gray-700 hover:text-brand-600"
              >
                {action.name || "(unnamed)"}
              </button>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-medium",
                  TYPE_COLORS[action.type],
                )}
              >
                {action.type}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <Toggle
                label=""
                checked={action.enabled}
                onChange={(v) => updateAction(i, { ...action, enabled: v })}
              />
              <button
                onClick={() => removeAction(i)}
                className="text-xs text-red-500 hover:text-red-700"
              >
                Remove
              </button>
            </div>
          </div>

          {expanded === i && (
            <ActionFields
              action={action}
              onChange={(a) => updateAction(i, a)}
            />
          )}
        </div>
      ))}

      <SaveBar mutation={mutation} dirty={dirty} onSave={handleSave} />
    </div>
  );
}
