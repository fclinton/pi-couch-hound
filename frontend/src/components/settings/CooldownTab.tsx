import { useState } from "react";
import { useUpdateConfigSection } from "@/api/config";
import type { AppConfig } from "@/api/types";
import { NumberInput, SaveBar } from "./FormFields";

interface Props {
  config: AppConfig;
}

export default function CooldownTab({ config }: Props) {
  const [seconds, setSeconds] = useState(config.cooldown.seconds);

  const mutation = useUpdateConfigSection();

  const dirty = seconds !== config.cooldown.seconds;

  const handleSave = () => {
    mutation.mutate({ section: "cooldown", data: { seconds } });
  };

  return (
    <div className="space-y-4">
      <NumberInput
        label="Cooldown (seconds)"
        value={seconds}
        onChange={setSeconds}
        min={0}
        max={300}
      />
      <p className="text-xs text-gray-500">
        Time to wait after a detection before triggering actions again (0–300s).
      </p>
      <SaveBar mutation={mutation} dirty={dirty} onSave={handleSave} />
    </div>
  );
}
