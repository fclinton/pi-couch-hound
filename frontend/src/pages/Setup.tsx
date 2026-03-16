import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useSetup } from "@/api/auth";
import { useUpdateConfigSection } from "@/api/config";
import { pollForRestart } from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

type Step = "account" | "ssl";

export default function Setup() {
  const [step, setStep] = useState<Step>("account");

  // Account state
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mismatch, setMismatch] = useState(false);

  // SSL state
  const [sslEnabled, setSslEnabled] = useState(false);
  const [selfSigned, setSelfSigned] = useState(true);
  const [certfile, setCertfile] = useState("");
  const [keyfile, setKeyfile] = useState("");

  // Restart state
  const [restarting, setRestarting] = useState(false);

  const navigate = useNavigate();
  const setup = useSetup();
  const sslMutation = useUpdateConfigSection();
  const setToken = useAuthStore((s) => s.setToken);

  function handleAccountSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirmPassword) {
      setMismatch(true);
      return;
    }
    setMismatch(false);
    setup.mutate(
      { username, password },
      {
        onSuccess: (data) => {
          setToken(data.access_token);
          setStep("ssl");
        },
      },
    );
  }

  function handleSslSubmit(e: FormEvent) {
    e.preventDefault();
    if (!sslEnabled) {
      navigate("/", { replace: true });
      return;
    }
    sslMutation.mutate(
      {
        section: "web",
        data: {
          ssl: {
            enabled: true,
            certfile: certfile || null,
            keyfile: keyfile || null,
            self_signed: selfSigned,
          },
        },
      },
      {
        onSuccess: (data) => {
          if (data._restart) {
            setRestarting(true);
            const targetBase = `https://${window.location.hostname}:${data.web.port}`;
            pollForRestart(targetBase).then(
              () => { window.location.href = `${targetBase}/`; },
              () => { window.location.href = `${targetBase}/`; },
            );
          } else {
            navigate("/", { replace: true });
          }
        },
      },
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-brand-600">Couch Hound</h1>
          <p className="mt-1 text-sm text-gray-500">
            {step === "account"
              ? "Welcome! Create an account to get started."
              : "Optionally enable HTTPS for secure access."}
          </p>
          <div className="mt-3 flex justify-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${step === "account" ? "bg-brand-500" : "bg-gray-300"}`}
            />
            <span
              className={`h-2 w-2 rounded-full ${step === "ssl" ? "bg-brand-500" : "bg-gray-300"}`}
            />
          </div>
        </div>

        {step === "account" && (
          <form
            onSubmit={handleAccountSubmit}
            className="space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
          >
            <label className="block space-y-1">
              <span className="text-sm font-medium text-gray-700">
                Username
              </span>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>

            <label className="block space-y-1">
              <span className="text-sm font-medium text-gray-700">
                Password
              </span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoFocus
                minLength={4}
                autoComplete="new-password"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>

            <label className="block space-y-1">
              <span className="text-sm font-medium text-gray-700">
                Confirm password
              </span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={4}
                autoComplete="new-password"
                className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </label>

            {mismatch && (
              <p className="text-sm text-red-600">Passwords do not match.</p>
            )}

            {setup.isError && (
              <p className="text-sm text-red-600">
                Setup failed. Please try again.
              </p>
            )}

            <button
              type="submit"
              disabled={setup.isPending}
              className="w-full rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {setup.isPending ? "Setting up..." : "Create account"}
            </button>
          </form>
        )}

        {step === "ssl" && (
          <form
            onSubmit={handleSslSubmit}
            className="space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
          >
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={sslEnabled}
                onChange={(e) => setSslEnabled(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
              />
              <div>
                <span className="text-sm font-medium text-gray-700">
                  Enable HTTPS
                </span>
                <p className="text-xs text-gray-500">
                  Serve the web interface over a secure connection
                </p>
              </div>
            </label>

            {sslEnabled && (
              <div className="space-y-3 rounded-md border border-gray-200 bg-gray-50 p-4">
                <label className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={selfSigned}
                    onChange={(e) => setSelfSigned(e.target.checked)}
                    className="mt-1 h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-700">
                      Use self-signed certificate
                    </span>
                    <p className="text-xs text-gray-500">
                      Automatically generate a certificate
                    </p>
                  </div>
                </label>

                {!selfSigned && (
                  <>
                    <label className="block space-y-1">
                      <span className="text-sm font-medium text-gray-700">
                        Certificate file path
                      </span>
                      <input
                        type="text"
                        value={certfile}
                        onChange={(e) => setCertfile(e.target.value)}
                        placeholder="/path/to/cert.pem"
                        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      />
                    </label>
                    <label className="block space-y-1">
                      <span className="text-sm font-medium text-gray-700">
                        Private key file path
                      </span>
                      <input
                        type="text"
                        value={keyfile}
                        onChange={(e) => setKeyfile(e.target.value)}
                        placeholder="/path/to/key.pem"
                        className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      />
                    </label>
                  </>
                )}
              </div>
            )}

            {sslMutation.isError && (
              <p className="text-sm text-red-600">
                Failed to save SSL settings. Please try again.
              </p>
            )}

            {restarting && (
              <div className="rounded-md border border-blue-200 bg-blue-50 p-3">
                <p className="text-sm text-blue-700">
                  Restarting server and redirecting to HTTPS...
                </p>
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => navigate("/", { replace: true })}
                className="flex-1 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Skip
              </button>
              <button
                type="submit"
                disabled={sslMutation.isPending}
                className="flex-1 rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {sslMutation.isPending ? "Saving..." : sslEnabled ? "Enable HTTPS" : "Finish"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
