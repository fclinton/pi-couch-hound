import { create } from "zustand";

interface AppState {
  connected: boolean;
  setConnected: (connected: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  connected: false,
  setConnected: (connected) => set({ connected }),
}));

export const useConnectionStatus = () => useAppStore((s) => s.connected);
