import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useSetup } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

export default function Setup() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mismatch, setMismatch] = useState(false);
  const navigate = useNavigate();
  const setup = useSetup();
  const setToken = useAuthStore((s) => s.setToken);

  function handleSubmit(e: FormEvent) {
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
          navigate("/", { replace: true });
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
            Welcome! Create an account to get started.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
        >
          <label className="block space-y-1">
            <span className="text-sm font-medium text-gray-700">Username</span>
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
            <span className="text-sm font-medium text-gray-700">Password</span>
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
      </div>
    </div>
  );
}
