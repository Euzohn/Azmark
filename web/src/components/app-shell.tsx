"use client";

import { Backpack, History, LogOut, Plane, Settings, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { LanguageToggle } from "@/components/language-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  key: TranslationKey;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/trips", key: "nav.trips", icon: Backpack },
  { href: "/flights", key: "nav.flights", icon: Plane },
  { href: "/audit", key: "nav.audit", icon: History },
  { href: "/settings", key: "nav.settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { token, user, setUser, clear } = useAuth();
  const { t } = useI18n();

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    if (!user) {
      api
        .me()
        .then(setUser)
        .catch(() => {
          // interceptor clears auth on 401
        });
    }
  }, [token, user, router, setUser]);

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        {t("common.loading")}
      </div>
    );
  }

  const logout = () => {
    clear();
    router.replace("/login");
  };

  const identity = user?.display_name ?? user?.username ?? "";

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col md:flex-row">
      <aside className="hidden md:flex md:w-56 md:flex-col md:gap-1 md:border-r md:border-border md:p-4">
        <div className="mb-6 px-2">
          <div className="text-lg font-semibold tracking-tight">{t("app.name")}</div>
          <div className="text-xs text-muted-foreground">{t("app.tagline")}</div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={pathname.startsWith(item.href)}
              label={t(item.key)}
            />
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-3 pt-6">
          <div className="px-2 text-xs text-muted-foreground">{identity}</div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <LanguageToggle />
            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              title={t("auth.logout")}
              aria-label={t("auth.logout")}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      <header className="flex items-center justify-between border-b border-border px-4 py-3 md:hidden">
        <span className="font-semibold">{t("app.name")}</span>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <LanguageToggle />
          <Button
            variant="ghost"
            size="icon"
            onClick={logout}
            aria-label={t("auth.logout")}
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <main className="flex-1 p-4 pb-24 md:p-8 md:pb-8">{children}</main>

      <nav
        className="fixed inset-x-0 bottom-0 z-10 flex border-t border-border bg-card md:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex min-h-12 flex-1 flex-col items-center justify-center gap-1 py-2 text-xs",
                active ? "text-primary" : "text-muted-foreground",
              )}
            >
              <Icon className="h-5 w-5" />
              {t(item.key)}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function NavLink({
  item,
  active,
  label,
}: {
  item: NavItem;
  active: boolean;
  label: string;
}) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm",
        active ? "bg-muted font-medium text-primary" : "text-muted-foreground hover:bg-muted",
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}
