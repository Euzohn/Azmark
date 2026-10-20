"use client";

import { Database, ScrollText, Shield, User } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo } from "react";

import { PageHeader } from "@/components/page-header";
import { Segmented, type SegmentedOption } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";

import AdminPanel from "../admin/page";
import AuditPanel from "../audit/page";
import DataPanel from "../data/page";
import SettingsPanel from "../settings/page";

type AccountTab = "profile" | "data" | "audit" | "admin";

function parseTab(value: string | null, allowAdmin: boolean): AccountTab {
  if (value === "data" || value === "audit") return value;
  if (value === "admin" && allowAdmin) return "admin";
  return "profile";
}

function AccountContent() {
  const { t } = useI18n();
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const isAdmin = user?.role === "ADMIN";
  const tab = parseTab(searchParams.get("tab"), isAdmin);

  const options = useMemo<SegmentedOption<AccountTab>[]>(
    () => [
      { value: "profile", label: t("account.tabs.profile"), icon: User },
      { value: "data", label: t("account.tabs.data"), icon: Database },
      { value: "audit", label: t("account.tabs.audit"), icon: ScrollText },
      ...(isAdmin
        ? [{ value: "admin" as const, label: t("account.tabs.admin"), icon: Shield }]
        : []),
    ],
    [t, isAdmin],
  );

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("account.title")} subtitle={t("account.subtitle")} />

      <div>
        <Segmented
          value={tab}
          onChange={(value) => router.replace(`/account?tab=${value}`)}
          options={options}
          size="md"
        />
      </div>

      <div className="animate-fade-in">
        {tab === "profile" ? <SettingsPanel embedded /> : null}
        {tab === "data" ? <DataPanel embedded /> : null}
        {tab === "audit" ? <AuditPanel embedded /> : null}
        {tab === "admin" && isAdmin ? <AdminPanel embedded /> : null}
      </div>
    </div>
  );
}

export default function AccountPage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-5">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-10 w-full max-w-md" />
          <Skeleton className="h-40 w-full" />
        </div>
      }
    >
      <AccountContent />
    </Suspense>
  );
}
