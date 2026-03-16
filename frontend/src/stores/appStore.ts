import { create } from "zustand";

interface AppState {
  connected: boolean;
  setConnected: (connected: boolean) => void;
  mobileMenuOpen: boolean;
  setMobileMenuOpen: (open: boolean) => void;
  toggleMobileMenu: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  connected: false,
  setConnected: (connected) => set({ connected }),
  mobileMenuOpen: false,
  setMobileMenuOpen: (open) => set({ mobileMenuOpen: open }),
  toggleMobileMenu: () => set((s) => ({ mobileMenuOpen: !s.mobileMenuOpen })),
}));

export const useConnectionStatus = () => useAppStore((s) => s.connected);
export const useMobileMenuOpen = () => useAppStore((s) => s.mobileMenuOpen);
export const useSetMobileMenuOpen = () => useAppStore((s) => s.setMobileMenuOpen);
export const useToggleMobileMenu = () => useAppStore((s) => s.toggleMobileMenu);
