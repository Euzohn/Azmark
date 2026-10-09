import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { User } from "@/lib/types";

interface AuthState {
  token: string | null;
  user: User | null;
  hasHydrated: boolean;
  setAuth: (token: string, user: User) => void;
  setUser: (user: User) => void;
  clear: () => void;
  setHasHydrated: (value: boolean) => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      hasHydrated: false,
      setAuth: (token, user) => set({ token, user }),
      setUser: (user) => set({ user }),
      clear: () => set({ token: null, user: null }),
      setHasHydrated: (value) => set({ hasHydrated: value }),
    }),
    {
      name: "azmark-auth",
      onRehydrateStorage: () => (state) => {
        if (state) state.setHasHydrated(true);
      },
    },
  ),
);
