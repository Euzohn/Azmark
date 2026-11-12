import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  hasHydrated: boolean;
  setUser: (user: User) => void;
  clear: () => void;
  setHasHydrated: (value: boolean) => void;
}

// The session JWT lives in an HttpOnly cookie set by the backend (spec #4.3);
// page scripts can never read it. Only the resolved user profile is persisted
// here for instant UI rendering — the shell re-validates it via /auth/me on
// mount, because the stored name alone proves nothing about the cookie.
//
// Legacy "azmark-auth" blobs (v0) carry a `token` key; it is dropped by
// `partialize` on the next write and nothing in the app reads it.
export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      hasHydrated: false,
      setUser: (user) => set({ user }),
      clear: () => set({ user: null }),
      setHasHydrated: (value) => set({ hasHydrated: value }),
    }),
    {
      name: "azmark-auth",
      partialize: (state) => ({ user: state.user }),
      onRehydrateStorage: () => (state) => {
        if (state) state.setHasHydrated(true);
      },
    },
  ),
);