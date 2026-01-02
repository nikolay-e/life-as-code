import { create } from "zustand";
import { api, ApiError } from "../../lib/api";
import type { User } from "../../types/api";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isInitialized: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  isInitialized: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.auth.login(username, password);
      set({
        user: response.user,
        isLoading: false,
      });
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Login failed. Please try again.";
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  logout: async () => {
    set({ isLoading: true });
    try {
      await api.auth.logout();
    } finally {
      set({
        user: null,
        isLoading: false,
      });
    }
  },

  checkAuth: async () => {
    set({ isLoading: true });
    try {
      const response = await api.auth.me();
      set({ user: response.user, isLoading: false, isInitialized: true });
    } catch {
      set({ user: null, isLoading: false, isInitialized: true });
    }
  },

  clearError: () => {
    set({ error: null });
  },
}));
