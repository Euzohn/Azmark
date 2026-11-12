"use client";

import { Database, Plug, ScrollText, Shield, UserRound, UserCog } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo } from "react";

import { PageHeader } from "@/components/page-header";
import { Segmented, type SegmentedOption } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";
import { usePageTitle } from "@/lib/page-title";

import AdminPanel from "../admin/page";
import AuditPanel from "../audit/page";
import DataPanel from "../data/page";
import { SettingsPanel } from "../settings/page";

type AccountTab = "profile" | "integrations" | "security" | "data" | "audit" | "admin";

function parseTab(value: string | null, allowAdmin: boolean): AccountTab {
  if (value === "data" || value === "audit") return value;
  if (value === "integrations" || value === "security") return value;
  if (value === "admin" && allowAdmin) return "admin";
  return "profile";
}

function AccountContent() {
  const { t } = useI18n();
  usePageTitle(t("nav.account"));
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const isAdmin = user?.role === "ADMIN";
  const tab = parseTab(searchParams.get("tab"), isAdmin);

  const options = useMemo<SegmentedOption<AccountTab>[]>(
    () => [
      { value: "profile", label: t("account.tabs.profile"), icon: UserRound },
      { value: "integrations", label: t("account.tabs.integrations"), icon: Plug },
      { value: "security", label: t("account.tabs.security"), icon: Shield },
      { value: "data", label: t("account.tabs.data"), icon: Database },
      { value: "audit", label: t("account.tabs.audit"), icon: ScrollText },
      ...(isAdmin
        ? [{ value: "admin" as const, label: t("account.tabs.admin"), icon: UserCog }]
        : []),
    ],
    [t, isAdmin],
  );

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("account.title")} subtitle={t("account.subtitle")} />

      <div className="-mx-1 overflow-x-auto px-1 pb-1">
        <Segmented
          value={tab}
          onChange={(value) => router.replace(`/account?tab=${value}`)}
          options={options}
          size="md"
        />
      </div>

      <div className="animate-fade-in">
        {tab === "profile" ? <SettingsPanel embedded section="profile" /> : null}
        {tab === "integrations" ? <SettingsPanel embedded section="integrations" /> : null}
        {tab === "security" ? <SettingsPanel embedded section="security" /> : null}
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
