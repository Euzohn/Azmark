"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ThemeProvider } from "@/components/theme-provider";
import { useAuth } from "@/lib/auth-store";
import { I18nProvider } from "@/lib/i18n";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );

  // Query keys are not user-scoped, so the cache must be wiped whenever the
  // signed-in account changes (logout, or switching accounts in the same tab).
  // Otherwise the next account renders the previous account's cached records
  // until refetch completes — a cross-account data leak. Cancel in-flight
  // queries first so a late response cannot repopulate the cleared cache.
  const userId = useAuth((s) => s.user?.id ?? null);
  useEffect(() => {
    void client.cancelQueries();
    client.clear();
  }, [client, userId]);

  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <I18nProvider>{children}</I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
