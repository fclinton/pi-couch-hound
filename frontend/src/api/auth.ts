import { useQuery, useMutation } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type {
  AuthStatusResponse,
  LoginRequest,
  LoginResponse,
  SetupRequest,
  SetupResponse,
} from "./types";

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

export function useSetup() {
  return useMutation({
    mutationFn: (data: SetupRequest) =>
      apiFetch<SetupResponse>("/auth/setup", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: { current_password: string; new_password: string }) =>
      apiFetch<{ message: string }>("/auth/change-password", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  });
}
