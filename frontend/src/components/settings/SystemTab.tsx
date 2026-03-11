import { useState } from "react";
import { useUpdateConfigSection } from "@/api/config";
import type { AppConfig } from "@/api/types";
import { TextInput, NumberInput, Toggle, SelectInput, SaveBar } from "./FormFields";

interface Props {
  config: AppConfig;
}

const LOG_LEVELS = [
  { value: "DEBUG", label: "DEBUG" },
  { value: "INFO", label: "INFO" },
  { value: "WARNING", label: "WARNING" },
  { value: "ERROR", label: "ERROR" },
];

export default function SystemTab({ config }: Props) {
  // Web state
  const [host, setHost] = useState(config.web.host);
  const [port, setPort] = useState(config.web.port);
  const [authEnabled, setAuthEnabled] = useState(config.web.auth.enabled);
  const [username, setUsername] = useState(config.web.auth.username);
  const [passwordHash, setPasswordHash] = useState(config.web.auth.password_hash);

  // Logging state
  const [level, setLevel] = useState(config.logging.level);
  const [logFile, setLogFile] = useState(config.logging.file);
  const [maxSizeMb, setMaxSizeMb] = useState(config.logging.max_size_mb);
  const [backupCount, setBackupCount] = useState(config.logging.backup_count);

  const webMutation = useUpdateConfigSection();
  const logMutation = useUpdateConfigSection();

  const webDirty =
    host !== config.web.host ||
    port !== config.web.port ||
    authEnabled !== config.web.auth.enabled ||
    username !== config.web.auth.username ||
    passwordHash !== config.web.auth.password_hash;

  const logDirty =
    level !== config.logging.level ||
    logFile !== config.logging.file ||
    maxSizeMb !== config.logging.max_size_mb ||
    backupCount !== config.logging.backup_count;

  const handleSaveWeb = () => {
    webMutation.mutate({
      section: "web",
      data: {
        host,
        port,
        auth: { enabled: authEnabled, username, password_hash: passwordHash },
      },
    });
  };

  const handleSaveLogging = () => {
    logMutation.mutate({
      section: "logging",
      data: { level, file: logFile, max_size_mb: maxSizeMb, backup_count: backupCount },
    });
  };

  return (
    <div className="space-y-8">
      {/* Web */}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Web Server</h3>
        <div className="grid grid-cols-2 gap-4">
          <TextInput label="Host" value={host} onChange={setHost} />
          <NumberInput label="Port" value={port} onChange={setPort} min={1} max={65535} />
        </div>
        <Toggle
          label="Enable authentication"
          checked={authEnabled}
          onChange={setAuthEnabled}
        />
        {authEnabled && (
          <div className="grid grid-cols-2 gap-4">
            <TextInput label="Username" value={username} onChange={setUsername} />
            <TextInput label="Password hash" value={passwordHash} onChange={setPasswordHash} />
          </div>
        )}
        <SaveBar mutation={webMutation} dirty={webDirty} onSave={handleSaveWeb} />
      </section>

      {/* Logging */}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Logging</h3>
        <div className="grid grid-cols-2 gap-4">
          <SelectInput label="Level" value={level} onChange={(v) => setLevel(v as typeof level)} options={LOG_LEVELS} />
          <TextInput label="Log file" value={logFile} onChange={setLogFile} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <NumberInput label="Max size (MB)" value={maxSizeMb} onChange={setMaxSizeMb} min={1} />
          <NumberInput label="Backup count" value={backupCount} onChange={setBackupCount} min={0} />
        </div>
        <SaveBar mutation={logMutation} dirty={logDirty} onSave={handleSaveLogging} />
      </section>
    </div>
  );
}
