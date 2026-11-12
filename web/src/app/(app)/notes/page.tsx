"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus, Search, StickyNote } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Fab } from "@/components/ui/fab";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { saveScroll, takeScroll } from "@/lib/scroll-memory";
import { useI18n } from "@/lib/i18n";
import { usePageTitle } from "@/lib/page-title";
import type { NoteFilters } from "@/lib/types";

function formatDate(value: string | null, locale: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function NotesContent() {
  const { t, locale } = useI18n();
  usePageTitle(t("nav.notes"));
  const searchParams = useSearchParams();
  const [search, setSearch] = useState(() => searchParams.get("search") ?? "");
  const [sort, setSort] = useState<NoteFilters["sort"]>("newest");

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["notes", { search, sort }],
    queryFn: () =>
      api.listNotes({ search: search || undefined, sort, page_size: 100 }),
  });

  // Keep the search term in the URL so it survives the trip to a detail page.
  useEffect(() => {
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    window.history.replaceState(null, "", `/notes${query}`);
  }, [search]);

  const scrollRestored = useRef(false);
  useEffect(() => {
    if (scrollRestored.current || !data) return;
    scrollRestored.current = true;
    const y = takeScroll(window.location.pathname + window.location.search);
    if (y === null) return;
    window.scrollTo(0, y);
    requestAnimationFrame(() => window.scrollTo(0, y));
  }, [data]);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("notes.title")}
        subtitle={data ? t("records.total", { count: data.total }) : t("notes.subtitle")}
        actions={
          <Link href="/notes/new">
            <Button className="hidden md:inline-flex">
              <Plus className="h-4 w-4" />
              {t("notes.add")}
            </Button>
          </Link>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-10"
            placeholder={t("notes.searchPlaceholder")}
            aria-label={t("common.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select
          aria-label={t("notes.sort.newest")}
          value={sort}
          onChange={(e) => setSort(e.target.value as NoteFilters["sort"])}
          className="sm:w-44"
        >
          <option value="newest">{t("notes.sort.newest")}</option>
          <option value="oldest">{t("notes.sort.oldest")}</option>
          <option value="updated">{t("notes.sort.updated")}</option>
          <option value="title">{t("notes.sort.title")}</option>
        </Select>
      </div>

      {isError ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-4 rounded-xl border border-danger/30 bg-card p-5"
        >
          <p className="text-sm text-danger">{t("common.error")}</p>
          <Button variant="outline" onClick={() => void refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      ) : isLoading ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={StickyNote}
          title={t("notes.empty")}
          hint={t("notes.emptyHint")}
          action={
            <Link href="/notes/new">
              <Button variant="outline">
                <Plus className="h-4 w-4" />
                {t("notes.add")}
              </Button>
            </Link>
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          {data.items.map((note) => (
            <Link
              key={note.id}
              href={`/notes/${note.id}?from=${encodeURIComponent(
                search ? `/notes?search=${encodeURIComponent(search)}` : "/notes",
              )}`}
              onClick={() => saveScroll(window.location.pathname + window.location.search)}
              className="group grid items-center gap-3 border-b border-border bg-card px-4 py-4 last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)_8rem] lg:gap-5 lg:px-5"
            >
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  <StickyNote className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{note.title}</div>
                  <div className="mt-1 line-clamp-1 text-xs text-muted-foreground lg:hidden">
                    {note.content || "—"}
                  </div>
                </div>
              </div>
              <div className="hidden truncate text-xs text-muted-foreground lg:block">
                {note.content || "—"}
              </div>
              <div className="pl-[3.25rem] text-xs text-muted-foreground lg:pl-0 lg:text-right">
                {formatDate(note.updated_at, locale)}
              </div>
            </Link>
          ))}
        </div>
      )}

      <Fab label={t("notes.add")} href="/notes/new">
        <Plus className="h-6 w-6" />
      </Fab>
    </div>
  );
}

export default function NotesPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-5">
          <Skeleton className="h-10 w-56" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      }
    >
      <NotesContent />
    </Suspense>
  );
}
