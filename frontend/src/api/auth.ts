import { useQuery, useMutation } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { AuthStatusResponse, LoginRequest, LoginResponse } from "./types";

export function useAuthStatus() {
  return useQuery({
    queryKey: ["authStatus"],
    queryFn: () => apiFetch<AuthStatusResponse>("/auth/status"),
    retry: false,
  });
}

export function useLogin() {
  return useMutation({
    mutationFn: (data: LoginRequest) =>
      apiFetch<LoginResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  });
}
