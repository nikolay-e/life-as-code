import { create } from "zustand";
import { api } from "@/lib/api";

interface User {
  id: number;
  username: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (
    username: string,
    password: string,
  ) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,

  login: async (username: string, password: string) => {
    try {
      const response = await api.post("/api/auth/login", {
        username,
        password,
      });
      if (response.ok) {
        const data = await response.json();
        set({ user: data.user, isAuthenticated: true });
        return { success: true };
      }
      const error = await response.json();
      return { success: false, error: error.message || "Invalid credentials" };
    } catch {
      return { success: false, error: "Network error" };
    }
  },

  logout: async () => {
    try {
      await api.post("/api/auth/logout");
    } finally {
      set({ user: null, isAuthenticated: false });
    }
  },

  checkAuth: async () => {
    try {
      const response = await api.get("/api/auth/me");
      if (response.ok) {
        const data = await response.json();
        set({ user: data.user, isAuthenticated: true, isLoading: false });
      } else {
        set({ user: null, isAuthenticated: false, isLoading: false });
      }
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));

useAuthStore.getState().checkAuth();
