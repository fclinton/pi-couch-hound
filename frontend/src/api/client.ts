import { getToken } from "@/stores/authStore";

const BASE_URL = "/api";

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json() as Promise<T>;
}

/**
 * Poll a URL's /api/health endpoint until the server comes back up after a restart.
 * Polls every 1s. Resolves when the server responds, or rejects after maxWait ms.
 */
export function pollForRestart(
  baseUrl: string,
  maxWait = 30000,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + maxWait;

    function poll() {
      if (Date.now() > deadline) {
        reject(new Error("Server did not restart in time"));
        return;
      }
      fetch(`${baseUrl}/api/health`, { mode: "no-cors" })
        .then(() => resolve())
        .catch(() => setTimeout(poll, 1000));
    }

    poll();
  });
}
