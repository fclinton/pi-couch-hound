import { getToken } from "@/stores/authStore";

const BASE_URL = "/api";

export interface FieldError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export class ApiValidationError extends Error {
  fieldErrors: FieldError[];

  constructor(fieldErrors: FieldError[]) {
    super("Validation failed");
    this.name = "ApiValidationError";
    this.fieldErrors = fieldErrors;
  }
}

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
    if (res.status === 422) {
      try {
        const body = await res.json();
        if (Array.isArray(body.detail)) {
          throw new ApiValidationError(body.detail as FieldError[]);
        }
      } catch (e) {
        if (e instanceof ApiValidationError) throw e;
      }
    }
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
