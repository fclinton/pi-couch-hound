import { useState } from "react";
import { useUpdateConfigSection } from "@/api/config";
import { pollForRestart } from "@/api/client";
import { useChangePassword } from "@/api/auth";
import { useUpdateStatus, useCheckForUpdate, useApplyUpdate } from "@/api/update";
import type { AppConfig } from "@/api/types";
import { TextInput, NumberInput, Toggle, SelectInput, SaveBar } from "./FormFields";
import { cn } from "@/lib/utils";

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

  // SSL state
  const [sslEnabled, setSslEnabled] = useState(config.web.ssl.enabled);
  const [certfile, setCertfile] = useState(config.web.ssl.certfile ?? "");
  const [keyfile, setKeyfile] = useState(config.web.ssl.keyfile ?? "");
  const [selfSigned, setSelfSigned] = useState(config.web.ssl.self_signed);

  // Password change state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const changePasswordMutation = useChangePassword();

  // Logging state
  const [level, setLevel] = useState(config.logging.level);
  const [logFile, setLogFile] = useState(config.logging.file);
  const [when, setWhen] = useState(config.logging.when);
  const [logInterval, setLogInterval] = useState(config.logging.interval);
  const [backupCount, setBackupCount] = useState(config.logging.backup_count);

  // Update state
  const [updateEnabled, setUpdateEnabled] = useState(config.update.enabled);
  const [checkInterval, setCheckInterval] = useState(config.update.check_interval_minutes);
  const [autoApply, setAutoApply] = useState(config.update.auto_apply);
  const [windowStart, setWindowStart] = useState(config.update.maintenance_window_start ?? "");
  const [windowEnd, setWindowEnd] = useState(config.update.maintenance_window_end ?? "");

  // Restart state for SSL changes
  const [restarting, setRestarting] = useState(false);

  const webMutation = useUpdateConfigSection();
  const logMutation = useUpdateConfigSection();
  const updateMutation = useUpdateConfigSection();

  const { data: updateStatus } = useUpdateStatus();
  const checkMutation = useCheckForUpdate();
  const applyMutation = useApplyUpdate();

  const webDirty =
    host !== config.web.host ||
    port !== config.web.port ||
    authEnabled !== config.web.auth.enabled ||
    username !== config.web.auth.username ||
    sslEnabled !== config.web.ssl.enabled ||
    certfile !== (config.web.ssl.certfile ?? "") ||
    keyfile !== (config.web.ssl.keyfile ?? "") ||
    selfSigned !== config.web.ssl.self_signed;

  const logDirty =
    level !== config.logging.level ||
    logFile !== config.logging.file ||
    when !== config.logging.when ||
    logInterval !== config.logging.interval ||
    backupCount !== config.logging.backup_count;

  const updateDirty =
    updateEnabled !== config.update.enabled ||
    checkInterval !== config.update.check_interval_minutes ||
    autoApply !== config.update.auto_apply ||
    windowStart !== (config.update.maintenance_window_start ?? "") ||
    windowEnd !== (config.update.maintenance_window_end ?? "");

  const handleSaveWeb = () => {
    webMutation.mutate(
      {
        section: "web",
        data: {
          host,
          port,
          auth: {
            enabled: authEnabled,
            username,
            password_hash: config.web.auth.password_hash,
          },
          ssl: {
            enabled: sslEnabled,
            certfile: certfile || null,
            keyfile: keyfile || null,
            self_signed: selfSigned,
          },
        },
      },
      {
        onSuccess: (data) => {
          if (!data._restart) return;
          setRestarting(true);
          const sslToggled = sslEnabled !== config.web.ssl.enabled;
          const newScheme = sslToggled
            ? (sslEnabled ? "https:" : "http:")
            : window.location.protocol;
          const targetBase = `${newScheme}//${window.location.hostname}:${port}`;
          pollForRestart(targetBase).then(
            () => {
              if (sslToggled) {
                window.location.href = `${targetBase}/`;
              } else {
                window.location.reload();
              }
            },
            () => {
              // Timeout — try redirecting anyway
              if (sslToggled) {
                window.location.href = `${targetBase}/`;
              } else {
                window.location.reload();
              }
            },
          );
        },
      },
    );
  };

  const handleChangePassword = () => {
    if (newPassword !== confirmPassword) return;
    changePasswordMutation.mutate(
      { current_password: currentPassword, new_password: newPassword },
      {
        onSuccess: () => {
          setCurrentPassword("");
          setNewPassword("");
          setConfirmPassword("");
        },
      },
    );
  };

  const handleSaveLogging = () => {
    logMutation.mutate({
      section: "logging",
      data: { level, file: logFile, when, interval: logInterval, backup_count: backupCount },
    });
  };

  const handleSaveUpdate = () => {
    updateMutation.mutate({
      section: "update",
      data: {
        enabled: updateEnabled,
        check_interval_minutes: checkInterval,
        auto_apply: autoApply,
        maintenance_window_start: windowStart || null,
        maintenance_window_end: windowEnd || null,
      },
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
          <>
            <TextInput label="Username" value={username} onChange={setUsername} />
            <div className="mt-4 space-y-3 rounded-md border border-gray-200 bg-gray-50 p-4">
              <h4 className="text-sm font-medium text-gray-700">Change password</h4>
              <TextInput
                label="Current password"
                value={currentPassword}
                onChange={setCurrentPassword}
              />
              <div className="grid grid-cols-2 gap-4">
                <TextInput
                  label="New password"
                  value={newPassword}
                  onChange={setNewPassword}
                />
                <TextInput
                  label="Confirm new password"
                  value={confirmPassword}
                  onChange={setConfirmPassword}
                />
              </div>
              {newPassword !== "" && confirmPassword !== "" && newPassword !== confirmPassword && (
                <p className="text-sm text-red-600">Passwords do not match.</p>
              )}
              {changePasswordMutation.isSuccess && (
                <p className="text-sm text-green-600">Password changed successfully.</p>
              )}
              {changePasswordMutation.isError && (
                <p className="text-sm text-red-600">
                  Failed to change password. Check your current password.
                </p>
              )}
              <button
                type="button"
                onClick={handleChangePassword}
                disabled={
                  changePasswordMutation.isPending ||
                  !currentPassword ||
                  !newPassword ||
                  newPassword !== confirmPassword
                }
                className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {changePasswordMutation.isPending ? "Changing..." : "Change password"}
              </button>
            </div>
          </>
        )}
        <div className="border-t border-gray-200 pt-4">
          <Toggle
            label="Enable HTTPS"
            description="Serve the web interface over HTTPS"
            checked={sslEnabled}
            onChange={setSslEnabled}
          />
        </div>
        {sslEnabled && (
          <div className="space-y-3 rounded-md border border-gray-200 bg-gray-50 p-4">
            <Toggle
              label="Use self-signed certificate"
              description="Automatically generate a self-signed certificate"
              checked={selfSigned}
              onChange={setSelfSigned}
            />
            {!selfSigned && (
              <div className="grid grid-cols-2 gap-4">
                <TextInput
                  label="Certificate file path"
                  value={certfile}
                  onChange={setCertfile}
                  placeholder="/path/to/cert.pem"
                />
                <TextInput
                  label="Private key file path"
                  value={keyfile}
                  onChange={setKeyfile}
                  placeholder="/path/to/key.pem"
                />
              </div>
            )}
          </div>
        )}
        {restarting && (
          <div className="rounded-md border border-blue-200 bg-blue-50 p-3">
            <p className="text-sm text-blue-700">
              {sslEnabled !== config.web.ssl.enabled
                ? "Restarting server and redirecting to new address..."
                : "Restarting server..."}
            </p>
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
          <SelectInput
            label="Rotate"
            value={when}
            onChange={setWhen}
            options={[
              { value: "midnight", label: "Midnight" },
              { value: "H", label: "Hourly" },
              { value: "D", label: "Daily" },
            ]}
          />
          <NumberInput label="Interval" value={logInterval} onChange={setLogInterval} min={1} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <NumberInput label="Backup count" value={backupCount} onChange={setBackupCount} min={0} />
        </div>
        <SaveBar mutation={logMutation} dirty={logDirty} onSave={handleSaveLogging} />
      </section>

      {/* Updates */}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">Software Updates</h3>
        <Toggle
          label="Enable automatic update checks"
          checked={updateEnabled}
          onChange={setUpdateEnabled}
        />
        {updateEnabled && (
          <>
            <NumberInput
              label="Check interval (minutes)"
              value={checkInterval}
              onChange={setCheckInterval}
              min={5}
              max={1440}
            />
            <Toggle
              label="Auto-apply updates"
              description="Automatically install updates during the maintenance window"
              checked={autoApply}
              onChange={setAutoApply}
            />
            {autoApply && (
              <div className="grid grid-cols-2 gap-4">
                <TextInput
                  label="Maintenance window start (HH:MM)"
                  value={windowStart}
                  onChange={setWindowStart}
                  placeholder="03:00"
                />
                <TextInput
                  label="Maintenance window end (HH:MM)"
                  value={windowEnd}
                  onChange={setWindowEnd}
                  placeholder="05:00"
                />
              </div>
            )}
          </>
        )}
        <SaveBar mutation={updateMutation} dirty={updateDirty} onSave={handleSaveUpdate} />

        {/* Update status & actions */}
        {updateStatus && (
          <div className="rounded-md border border-gray-200 bg-gray-50 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-sm text-gray-700">
                  Version: <span className="font-mono font-medium">{updateStatus.current_version}</span>
                  {updateStatus.current_commit && (
                    <span className="ml-2 text-gray-500">({updateStatus.current_commit})</span>
                  )}
                </p>
                {updateStatus.last_check_time && (
                  <p className="text-xs text-gray-500">
                    Last checked: {new Date(updateStatus.last_check_time).toLocaleString()}
                  </p>
                )}
              </div>
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                  updateStatus.state === "up_to_date" && "bg-green-100 text-green-800",
                  updateStatus.state === "available" && "bg-yellow-100 text-yellow-800",
                  updateStatus.state === "checking" && "bg-blue-100 text-blue-800",
                  updateStatus.state === "applying" && "bg-blue-100 text-blue-800",
                  updateStatus.state === "error" && "bg-red-100 text-red-800",
                )}
              >
                {updateStatus.state === "up_to_date" && "Up to date"}
                {updateStatus.state === "available" && `${updateStatus.commits_behind} update(s) available`}
                {updateStatus.state === "checking" && "Checking..."}
                {updateStatus.state === "applying" && "Applying..."}
                {updateStatus.state === "error" && "Error"}
              </span>
            </div>

            {updateStatus.state === "available" && (
              <div className="space-y-1">
                {updateStatus.available_version && (
                  <p className="text-sm text-gray-700">
                    New version: <span className="font-mono font-medium">{updateStatus.available_version}</span>
                  </p>
                )}
                {updateStatus.commit_messages.length > 0 && (
                  <ul className="list-disc pl-5 text-xs text-gray-600 space-y-0.5">
                    {updateStatus.commit_messages.slice(0, 5).map((msg, i) => (
                      <li key={i}>{msg}</li>
                    ))}
                    {updateStatus.commit_messages.length > 5 && (
                      <li>...and {updateStatus.commit_messages.length - 5} more</li>
                    )}
                  </ul>
                )}
              </div>
            )}

            {updateStatus.state === "error" && updateStatus.last_error && (
              <p className="text-sm text-red-600">{updateStatus.last_error}</p>
            )}

            {updateStatus.state === "applying" && (
              <p className="text-sm text-blue-600">Applying update and restarting... The page will reload automatically.</p>
            )}

            <div className="flex gap-2">
              <button
                onClick={() => checkMutation.mutate()}
                disabled={checkMutation.isPending || updateStatus.state === "checking" || updateStatus.state === "applying"}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium",
                  checkMutation.isPending || updateStatus.state === "checking"
                    ? "cursor-not-allowed bg-gray-200 text-gray-500"
                    : "bg-gray-200 text-gray-700 hover:bg-gray-300",
                )}
              >
                {checkMutation.isPending || updateStatus.state === "checking" ? "Checking..." : "Check Now"}
              </button>
              {updateStatus.state === "available" && (
                <button
                  onClick={() => {
                    if (window.confirm("This will restart the application. Continue?")) {
                      applyMutation.mutate();
                    }
                  }}
                  disabled={applyMutation.isPending}
                  className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-600"
                >
                  {applyMutation.isPending ? "Applying..." : "Apply Update"}
                </button>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
