"use client";

import {
  Backpack,
  BarChart3,
  Home,
  History,
  LogOut,
  type LucideIcon,
  Map as MapIcon,
  MoreHorizontal,
  Plane,
  ScrollText,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { LanguageToggle } from "@/components/language-toggle";
import { ThemeToggle } from "@/components/theme-toggle";
import { BottomSheet } from "@/components/ui/bottom-sheet";
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
  { href: "/dashboard", key: "nav.dashboard", icon: Home },
  { href: "/trips", key: "nav.trips", icon: Backpack },
  { href: "/flights", key: "nav.flights", icon: Plane },
  { href: "/timeline", key: "nav.timeline", icon: History },
  { href: "/map", key: "nav.map", icon: MapIcon },
  { href: "/statistics", key: "nav.stats", icon: BarChart3 },
  { href: "/audit", key: "nav.audit", icon: ScrollText },
  { href: "/settings", key: "nav.settings", icon: Settings },
];

const MOBILE_MAIN: NavItem[] = [
  { href: "/dashboard", key: "nav.dashboard", icon: Home },
  { href: "/trips", key: "nav.trips", icon: Backpack },
  { href: "/flights", key: "nav.flights", icon: Plane },
  { href: "/map", key: "nav.map", icon: MapIcon },
];

const MOBILE_MORE: NavItem[] = [
  { href: "/timeline", key: "nav.timeline", icon: History },
  { href: "/statistics", key: "nav.stats", icon: BarChart3 },
  { href: "/audit", key: "nav.audit", icon: ScrollText },
  { href: "/settings", key: "nav.settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { token, user, setUser, clear, hasHydrated } = useAuth();
  const { t } = useI18n();
  const [moreOpen, setMoreOpen] = useState(false);

  useEffect(() => {
    if (!hasHydrated) return;
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
  }, [hasHydrated, token, user, router, setUser]);

  if (!hasHydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        {t("common.loading")}
      </div>
    );
  }

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
  const moreActive = MOBILE_MORE.some((item) => pathname.startsWith(item.href));

  return (
    <div className="bg-glow mx-auto flex min-h-dvh w-full max-w-6xl flex-col md:flex-row">
      <aside className="hidden md:sticky md:top-0 md:flex md:h-dvh md:w-60 md:shrink-0 md:flex-col md:gap-1 md:overflow-y-auto md:border-r md:border-border md:px-5 md:py-8">
        <div className="mb-8 flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#c26b30] to-primary text-primary-foreground shadow-md shadow-primary/25">
            <Backpack className="h-5 w-5" strokeWidth={1.75} />
          </div>
          <div>
            <div className="font-display text-xl font-semibold leading-none tracking-tight">
              {t("app.name")}
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">{t("app.tagline")}</div>
          </div>
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
          <div className="rounded-2xl border border-border bg-card px-3 py-2.5">
            <div className="truncate text-sm font-medium text-foreground">{identity}</div>
            <div className="truncate text-[11px] text-muted-foreground">{user?.username}</div>
          </div>
          <div className="flex items-center justify-center gap-1">
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

      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-background/90 px-4 py-3 backdrop-blur-md md:hidden">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#c26b30] to-primary text-primary-foreground">
            <Backpack className="h-4 w-4" strokeWidth={1.75} />
          </div>
          <span className="font-display text-lg font-semibold tracking-tight">{t("app.name")}</span>
        </div>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <LanguageToggle />
          <Button variant="ghost" size="icon" onClick={logout} aria-label={t("auth.logout")}>
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </header>

      <main className="flex-1 px-4 pb-28 pt-5 md:px-8 md:pb-10 md:pt-8">{children}</main>

      <nav
        className="fixed inset-x-0 bottom-0 z-20 flex border-t border-border bg-card/90 backdrop-blur-md md:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        {MOBILE_MAIN.map((item) => {
          const Icon = item.icon;
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex min-h-14 flex-1 cursor-pointer flex-col items-center justify-center gap-1 py-2 text-xs transition-colors duration-150",
                active ? "text-primary" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <span
                className={cn(
                  "flex h-8 w-14 items-center justify-center rounded-full transition-colors duration-150",
                  active ? "bg-accent text-accent-foreground" : "text-inherit",
                )}
              >
                <Icon className="h-5 w-5" strokeWidth={active ? 2 : 1.75} />
              </span>
              {t(item.key)}
            </Link>
          );
        })}
        <button
          type="button"
          onClick={() => setMoreOpen(true)}
          className={cn(
            "flex min-h-14 flex-1 cursor-pointer flex-col items-center justify-center gap-1 py-2 text-xs transition-colors duration-150",
            moreActive ? "text-primary" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <span
            className={cn(
              "flex h-8 w-14 items-center justify-center rounded-full transition-colors duration-150",
              moreActive ? "bg-accent text-accent-foreground" : "text-inherit",
            )}
          >
            <MoreHorizontal className="h-5 w-5" strokeWidth={moreActive ? 2 : 1.75} />
          </span>
          {t("nav.more")}
        </button>
      </nav>

      <BottomSheet open={moreOpen} onClose={() => setMoreOpen(false)} title={t("nav.moreTitle")}>
        {MOBILE_MORE.map((item) => {
          const Icon = item.icon;
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMoreOpen(false)}
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors",
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-foreground hover:bg-accent/60",
              )}
            >
              <Icon className="h-4 w-4" strokeWidth={active ? 2.25 : 1.75} />
              {t(item.key)}
            </Link>
          );
        })}
      </BottomSheet>
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
        "flex cursor-pointer items-center gap-3 rounded-full px-4 py-2.5 text-sm font-medium transition-colors duration-150",
        active
          ? "bg-primary text-primary-foreground shadow-sm shadow-primary/25"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
      )}
    >
      <Icon className="h-4 w-4" strokeWidth={active ? 2.25 : 1.75} />
      {label}
    </Link>
  );
}
