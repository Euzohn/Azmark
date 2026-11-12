"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Backpack,
  BarChart3,
  BedDouble,
  Bot,
  CalendarDays,
  ChevronRight,
  ClipboardCheck,
  Home,
  List as ListIcon,
  LogOut,
  type LucideIcon,
  Map as MapIcon,
  MapPin,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Receipt,
  StickyNote,
  User,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AzmarkLoader } from "@/components/azmark-loader";
import { AzmarkMark } from "@/components/azmark-mark";
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
  adminOnly?: boolean;
}

interface NavGroup {
  key: TranslationKey;
  items: NavItem[];
}

// Grouped by intent instead of one flat 13-item list: see the travels,
// manage the archive, work with the assistant. Account lives in the footer
// user card, which is where people expect identity-related settings.
const NAV_GROUPS: NavGroup[] = [
  {
    key: "nav.group.overview",
    items: [
      { href: "/dashboard", key: "nav.dashboard", icon: Home },
      { href: "/map", key: "nav.map", icon: MapIcon },
      { href: "/statistics", key: "nav.stats", icon: BarChart3 },
    ],
  },
  {
    key: "nav.group.archive",
    items: [
      { href: "/trips", key: "nav.trips", icon: Backpack },
      { href: "/records", key: "nav.records", icon: ListIcon },
      { href: "/hotels", key: "nav.hotels", icon: BedDouble },
      { href: "/places", key: "nav.places", icon: MapPin },
      { href: "/activities", key: "nav.activities", icon: CalendarDays },
      { href: "/expenses", key: "nav.expenses", icon: Receipt },
      { href: "/notes", key: "nav.notes", icon: StickyNote },
    ],
  },
  {
    key: "nav.group.assistant",
    items: [
      { href: "/ai", key: "nav.ai", icon: Bot },
      { href: "/pending", key: "nav.pending", icon: ClipboardCheck },
    ],
  },
];

function isNavActive(href: string, pathname: string): boolean {
  // Flight/train/other detail routes live outside /records but belong to it.
  if (href === "/records") {
    return ["/records", "/flights", "/trains", "/transports"].some((base) =>
      pathname.startsWith(base),
    );
  }
  if (href === "/hotels") {
    return pathname.startsWith("/hotels");
  }
  // The old settings/data/audit/admin routes are now tabs under /account.
  if (href === "/account") {
    return ["/account", "/settings", "/data", "/audit", "/admin"].some((base) =>
      pathname.startsWith(base),
    );
  }
  return pathname.startsWith(href);
}

const MOBILE_MAIN: NavItem[] = [
  { href: "/dashboard", key: "nav.dashboard", icon: Home },
  { href: "/records", key: "nav.records", icon: ListIcon },
  { href: "/trips", key: "nav.trips", icon: Backpack },
  { href: "/map", key: "nav.map", icon: MapIcon },
];

const MOBILE_MORE: NavItem[] = [
  { href: "/hotels", key: "nav.hotels", icon: BedDouble },
  { href: "/places", key: "nav.places", icon: MapPin },
  { href: "/activities", key: "nav.activities", icon: CalendarDays },
  { href: "/expenses", key: "nav.expenses", icon: Receipt },
  { href: "/notes", key: "nav.notes", icon: StickyNote },
  { href: "/ai", key: "nav.ai", icon: Bot },
  { href: "/pending", key: "nav.pending", icon: ClipboardCheck },
  { href: "/statistics", key: "nav.stats", icon: BarChart3 },
  { href: "/account", key: "nav.account", icon: User },
];

const SIDEBAR_COLLAPSE_KEY = "azmark-sidebar-collapsed";

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, setUser, clear, hasHydrated } = useAuth();
  const { t } = useI18n();
  const [moreOpen, setMoreOpen] = useState(false);
  // The session lives in an HttpOnly cookie (spec #4.3), which scripts cannot
  // read. Resolving it means asking the backend; until /auth/me answers, the
  // shell stays on the loader so nothing renders for a stale persisted user.
  const [sessionReady, setSessionReady] = useState(false);
  // Read the collapse preference lazily so it is already correct on the first
  // sidebar render (SSR never reaches the aside: it renders behind the auth
  // loader), avoiding both a flash and a synchronous setState in an effect.
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(SIDEBAR_COLLAPSE_KEY) === "1";
  });

  // Live badge for the approval queue. Shares the "pending-actions" key
  // prefix so confirm/reject on the Pending page refreshes it immediately;
  // the interval picks up proposals submitted by agents in the meantime.
  // page_size=1 keeps the payload tiny — only pending_total is used. The key
  // is user-scoped so switching accounts never flashes the previous user's
  // count from cache.
  const { data: pendingData } = useQuery({
    queryKey: ["pending-actions", "sidebar-badge", user?.id ?? null],
    queryFn: () => api.listPendingActions({ status: "pending", page_size: 1 }),
    enabled: !!user,
    refetchInterval: 60_000,
  });
  const pendingCount = pendingData?.pending_total ?? 0;

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(SIDEBAR_COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  };

  useEffect(() => {
    if (!hasHydrated) return;
    // Validate the cookie session on every mount: the persisted user name
    // alone proves nothing about the cookie that actually authenticates us.
    api
      .me()
      .then(setUser)
      .catch(() => {
        // The interceptor clears auth on 401; land on the login form.
        clear();
        router.replace("/login");
      })
      .finally(() => setSessionReady(true));
  }, [hasHydrated, router, setUser, clear]);

  // Mid-session expiry: any 401 clears the user, so send the visitor back to
  // the login form instead of freezing on a loader.
  useEffect(() => {
    if (hasHydrated && sessionReady && !user) {
      router.replace("/login");
    }
  }, [hasHydrated, sessionReady, user, router]);

  if (!hasHydrated || !sessionReady || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <AzmarkLoader className="h-20 w-auto text-foreground" label={t("common.loading")} />
      </div>
    );
  }

  const logout = () => {
    // Record logout for the audit trail, but never block signing out.
    void api.logout().catch(() => {});
    clear();
    router.replace("/login");
  };

  const identity = user?.display_name ?? user?.username ?? "";
  const isAdmin = user?.role === "ADMIN";
  const navGroups = NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.adminOnly || isAdmin),
  })).filter((group) => group.items.length > 0);
  const mobileMoreItems = MOBILE_MORE.filter((item) => !item.adminOnly || isAdmin);
  const moreActive = MOBILE_MORE.some((item) => isNavActive(item.href, pathname));
  const accountActive = isNavActive("/account", pathname);
  const pendingBadgeLabel =
    pendingCount > 0 ? t("nav.pendingCount", { count: pendingCount }) : undefined;

  return (
    <div className="flex min-h-dvh w-full flex-col md:flex-row">
      {/* Keyboard shortcut: jump past the sidebar straight to the content (spec #95). */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-card focus:px-3 focus:py-2 focus:text-sm focus:shadow-lg focus:ring-2 focus:ring-ring"
      >
        {t("a11y.skipToContent")}
      </a>
      <aside
        className={cn(
          "hidden bg-card transition-[width] duration-200 ease-in-out md:sticky md:top-0 md:flex md:h-dvh md:shrink-0 md:flex-col md:overflow-hidden md:border-r md:border-border",
          collapsed ? "md:w-[4.5rem] md:px-2" : "md:w-56 md:px-3 lg:w-60",
        )}
      >
        {/* Brand — fixed while the nav scrolls */}
        <div
          className={cn(
            "shrink-0",
            collapsed
              ? "flex flex-col items-center gap-1.5 px-2 pb-3 pt-6"
              : "flex items-center gap-3 px-2 pb-4 pt-6",
          )}
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-foreground text-background">
            <AzmarkMark className="h-5 w-auto" />
          </div>
          {!collapsed ? (
            <>
              <div className="min-w-0 flex-1">
                <div className="font-display text-xl font-semibold leading-none tracking-tight">
                  {t("app.name")}
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">{t("app.tagline")}</div>
              </div>
              <button
                type="button"
                onClick={toggleCollapsed}
                title={t("nav.collapse")}
                aria-label={t("nav.collapse")}
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground/60 transition-colors hover:bg-muted hover:text-foreground"
              >
                <PanelLeftClose className="h-3.5 w-3.5" />
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={toggleCollapsed}
              title={t("nav.expand")}
              aria-label={t("nav.expand")}
              className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground/60 transition-colors hover:bg-muted hover:text-foreground"
            >
              <PanelLeftOpen className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Navigation — the only scrolling zone, with a palette-tinted scrollbar */}
        <nav className="nav-scroll min-h-0 flex-1 overflow-y-auto overflow-x-hidden pb-3">
          {navGroups.map((group, index) => (
            <section key={group.key} aria-label={t(group.key)}>
              {collapsed ? (
                index > 0 ? (
                  <div aria-hidden className="mx-2 my-2 border-t border-border/60" />
                ) : null
              ) : (
                <h2
                  className={cn(
                    "px-3 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground/70",
                    index === 0 ? "pt-1" : "pt-4",
                  )}
                >
                  {t(group.key)}
                </h2>
              )}
              <div className="flex flex-col gap-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.href}
                    item={item}
                    active={isNavActive(item.href, pathname)}
                    label={t(item.key)}
                    collapsed={collapsed}
                    badge={item.href === "/pending" ? pendingCount : 0}
                    badgeLabel={item.href === "/pending" ? pendingBadgeLabel : undefined}
                  />
                ))}
              </div>
            </section>
          ))}
        </nav>

        {/* Identity + utilities — fixed at the bottom */}
        <div
          className={cn(
            "shrink-0 border-t border-border/70 pb-4 pt-3",
            collapsed ? "px-0" : "px-3",
          )}
        >
          <Link
            href="/account"
            aria-current={accountActive ? "page" : undefined}
            title={collapsed ? t("nav.account") : undefined}
            className={cn(
              "group flex items-center gap-3 rounded-xl transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              collapsed ? "justify-center p-1.5" : "px-2 py-2",
              accountActive ? "bg-accent text-accent-foreground" : "hover:bg-muted/70",
            )}
          >
            <span
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-xs font-semibold transition-colors",
                accountActive ? "bg-primary/15 text-primary" : "bg-muted text-foreground",
              )}
            >
              {identity.slice(0, 2).toUpperCase() || "AZ"}
            </span>
            {!collapsed ? (
              <>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-foreground">
                    {identity}
                  </span>
                  <span className="block truncate text-[11px] text-muted-foreground">
                    @{user?.username}
                  </span>
                </span>
                <ChevronRight
                  aria-hidden
                  className="h-4 w-4 shrink-0 text-muted-foreground/50 transition-transform duration-150 group-hover:translate-x-0.5"
                />
              </>
            ) : null}
          </Link>
          <div
            className={cn(
              "mt-2 items-center",
              collapsed ? "grid grid-cols-2 justify-items-center" : "flex gap-0.5",
            )}
          >
            <ThemeToggle className={collapsed ? "h-7 w-7" : "h-8 w-8"} />
            <LanguageToggle compact={collapsed} className={collapsed ? "h-7 w-7" : "h-8"} />
            <a
              href="https://github.com/Euzohn/Azmark"
              target="_blank"
              rel="noopener noreferrer"
              title={t("app.github")}
              aria-label={t("app.github")}
              className={cn(
                "flex items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                collapsed ? "h-7 w-7" : "h-8 w-8",
              )}
            >
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden className="h-3.5 w-3.5">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.431 9.8 8.207 11.387.6.111.82-.258.82-.576 0-.285-.011-1.04-.017-2.041-3.334.724-4.041-1.61-4.041-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.084-.731.084-.731 1.205.085 1.84 1.236 1.84 1.236 1.07 1.834 2.807 1.305 3.492.997.108-.775.418-1.305.762-1.604-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .317.219.69.825.57C20.568 21.795 24 17.3 24 12c0-6.627-5.373-12-12-12" />
              </svg>
            </a>
            {!collapsed ? <div className="flex-1" /> : null}
            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              title={t("auth.logout")}
              aria-label={t("auth.logout")}
              className={cn(
                "text-muted-foreground hover:text-danger",
                collapsed ? "h-7 w-7" : "h-8 w-8",
              )}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-background/90 px-4 py-3 backdrop-blur-md md:hidden">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-foreground text-background">
            <AzmarkMark className="h-4 w-auto" />
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

      <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 px-4 pb-[calc(7rem+env(safe-area-inset-bottom))] pt-6 outline-none md:px-8 md:pb-12 md:pt-9 lg:px-10">
        <div className={cn("mx-auto w-full", pathname.startsWith("/map") ? "max-w-none" : "max-w-[1440px]")}>{children}</div>
      </main>

      <nav
        className="fixed inset-x-0 bottom-0 z-20 flex border-t border-border bg-card/90 backdrop-blur-md md:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        {MOBILE_MAIN.map((item) => {
          const Icon = item.icon;
          const active = isNavActive(item.href, pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex min-h-14 flex-1 cursor-pointer flex-col items-center justify-center gap-1 py-2 text-xs transition-colors duration-150",
                active ? "text-primary" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <span
                className={cn(
                  "flex h-8 w-14 items-center justify-center rounded-full transition-all duration-200",
                  active ? "scale-105 bg-accent text-accent-foreground" : "text-inherit",
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
              "flex h-8 w-14 items-center justify-center rounded-full transition-all duration-200",
              moreActive ? "scale-105 bg-accent text-accent-foreground" : "text-inherit",
            )}
          >
            <MoreHorizontal className="h-5 w-5" strokeWidth={moreActive ? 2 : 1.75} />
          </span>
          {t("nav.more")}
        </button>
      </nav>

      <BottomSheet open={moreOpen} onClose={() => setMoreOpen(false)} title={t("nav.moreTitle")}>
        {mobileMoreItems.map((item) => {
          const Icon = item.icon;
          const active = isNavActive(item.href, pathname);
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
  collapsed,
  badge = 0,
  badgeLabel,
}: {
  item: NavItem;
  active: boolean;
  label: string;
  collapsed: boolean;
  badge?: number;
  badgeLabel?: string;
}) {
  const Icon = item.icon;
  const badgeText = badge > 99 ? "99+" : String(badge);
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      title={collapsed ? (badgeLabel ? `${label} · ${badgeLabel}` : label) : undefined}
      className={cn(
        "relative flex cursor-pointer items-center rounded-lg py-2 text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:scale-[0.98]",
        collapsed ? "justify-center" : "gap-3 px-3",
        active
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:bg-muted/70 hover:text-foreground",
      )}
    >
      {active ? (
        <span
          aria-hidden
          className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-primary"
        />
      ) : null}
      <Icon
        className={cn("h-4 w-4 shrink-0", active && "text-primary")}
        strokeWidth={active ? 2.25 : 1.75}
      />
      {!collapsed ? <span className="min-w-0 truncate">{label}</span> : null}
      {badge > 0 ? (
        collapsed ? (
          <span
            aria-hidden
            className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-warning px-1 text-[9px] font-bold tabular-nums text-warning-foreground"
          >
            {badgeText}
          </span>
        ) : (
          <span
            aria-hidden
            className="ml-auto flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-warning/15 px-1.5 text-[10px] font-semibold tabular-nums text-warning"
          >
            {badgeText}
          </span>
        )
      ) : null}
      {badge > 0 && badgeLabel ? <span className="sr-only">{badgeLabel}</span> : null}
    </Link>
  );
}