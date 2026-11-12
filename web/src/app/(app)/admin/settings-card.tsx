"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Settings2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";
import type { AdminSettings } from "@/lib/types";

function CheckboxRow({
  id,
  label,
  hint,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-border px-3 py-2.5">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 h-4 w-4 shrink-0 accent-primary"
      />
      <span className="flex flex-col gap-0.5">
        <span className="text-sm font-medium">{label}</span>
        {hint ? <span className="text-xs text-muted-foreground">{hint}</span> : null}
      </span>
    </label>
  );
}

function SettingsForm({ initial }: { initial: AdminSettings }) {
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [allowRegistration, setAllowRegistration] = useState(initial.allow_registration);
  const [captchaEnabled, setCaptchaEnabled] = useState(initial.registration_captcha_enabled);
  const [captchaProvider, setCaptchaProvider] = useState(initial.captcha_provider);
  const [turnstileSiteKey, setTurnstileSiteKey] = useState(initial.turnstile_site_key ?? "");
  const [turnstileSecret, setTurnstileSecret] = useState("");
  const [smtpHost, setSmtpHost] = useState(initial.smtp_host ?? "");
  const [smtpPort, setSmtpPort] = useState(initial.smtp_port ? String(initial.smtp_port) : "");
  const [smtpUsername, setSmtpUsername] = useState(initial.smtp_username ?? "");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpSender, setSmtpSender] = useState(initial.smtp_sender ?? "");
  const [smtpStarttls, setSmtpStarttls] = useState(initial.smtp_starttls);
  const [testTo, setTestTo] = useState("");
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const save = useMutation({
    mutationFn: () =>
      api.updateAdminSettings({
        allow_registration: allowRegistration,
        registration_captcha_enabled: captchaEnabled,
        captcha_provider: captchaProvider,
        turnstile_site_key: turnstileSiteKey.trim(),
        ...(turnstileSecret ? { turnstile_secret: turnstileSecret } : {}),
        smtp_host: smtpHost.trim(),
        smtp_port: smtpPort ? Number(smtpPort) : null,
        smtp_username: smtpUsername.trim(),
        smtp_sender: smtpSender.trim(),
        smtp_starttls: smtpStarttls,
        ...(smtpPassword ? { smtp_password: smtpPassword } : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-settings"] });
      queryClient.invalidateQueries({ queryKey: ["admin-logs"] });
      setSmtpPassword("");
      setTurnstileSecret("");
      setNotice({ kind: "ok", text: t("admin.saved") });
    },
    onError: () => setNotice({ kind: "error", text: t("admin.saveFailed") }),
  });

  const sendTest = useMutation({
    mutationFn: () => api.testAdminEmail(testTo.trim() || undefined),
    onSuccess: () =>
      setNotice({
        kind: "ok",
        // Mirrors the backend fallback: the typed address, else the admin's
        // own account email.
        text: t("admin.testEmailSent", { to: testTo.trim() || user?.email || "—" }),
      }),
    onError: (err) => {
      const detail = err instanceof ApiError ? err.message : String(err);
      setNotice({ kind: "error", text: t("admin.testEmailFailed", { error: detail }) });
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-foreground">{t("admin.registration")}</h3>
        <div className="grid gap-2">
          <CheckboxRow
            id="allow-registration"
            label={t("admin.allowRegistration")}
            hint={t("admin.allowRegistrationHint")}
            checked={allowRegistration}
            onChange={setAllowRegistration}
          />
          <CheckboxRow
            id="registration-captcha"
            label={t("admin.captchaEnabled")}
            hint={t("admin.captchaEnabledHint")}
            checked={captchaEnabled}
            onChange={setCaptchaEnabled}
          />
        </div>
        {captchaEnabled ? (
          <div className="grid gap-3 rounded-lg border border-border p-3 sm:grid-cols-2">
            <div>
              <Label className="mb-1.5 block" htmlFor="captcha-provider">
                {t("admin.captchaProvider")}
              </Label>
              <Select
                id="captcha-provider"
                value={captchaProvider}
                onChange={(event) => setCaptchaProvider(event.target.value as "arithmetic" | "turnstile")}
              >
                <option value="arithmetic">{t("admin.captchaProvider.arithmetic")}</option>
                <option value="turnstile">{t("admin.captchaProvider.turnstile")}</option>
              </Select>
              {captchaProvider === "turnstile" ? (
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {t("admin.captchaProviderHint")}
                </p>
              ) : null}
            </div>
            {captchaProvider === "turnstile" ? (
              <div className="flex flex-col gap-3 sm:col-span-2 sm:grid sm:grid-cols-2">
                <div>
                  <Label className="mb-1.5 block" htmlFor="turnstile-site-key">
                    {t("admin.turnstileSiteKey")}
                  </Label>
                  <Input
                    id="turnstile-site-key"
                    value={turnstileSiteKey}
                    onChange={(event) => setTurnstileSiteKey(event.target.value)}
                    autoComplete="off"
                  />
                </div>
                <div>
                  <Label className="mb-1.5 block" htmlFor="turnstile-secret-key">
                    {t("admin.turnstileSecretKey")}
                  </Label>
                  <Input
                    id="turnstile-secret-key"
                    type="password"
                    value={turnstileSecret}
                    onChange={(event) => setTurnstileSecret(event.target.value)}
                    autoComplete="new-password"
                    placeholder={initial.turnstile_secret_set ? t("admin.turnstileSecretSet") : undefined}
                  />
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-foreground">{t("admin.smtpTitle")}</h3>
        <p className="text-xs text-muted-foreground">{t("admin.smtpHint")}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label className="mb-1.5 block" htmlFor="smtp-host">
              {t("admin.smtpHost")}
            </Label>
            <Input
              id="smtp-host"
              value={smtpHost}
              onChange={(event) => setSmtpHost(event.target.value)}
              placeholder="smtp.example.com"
            />
          </div>
          <div>
            <Label className="mb-1.5 block" htmlFor="smtp-port">
              {t("admin.smtpPort")}
            </Label>
            <Input
              id="smtp-port"
              value={smtpPort}
              onChange={(event) => setSmtpPort(event.target.value)}
              inputMode="numeric"
              placeholder="587"
            />
          </div>
          <div>
            <Label className="mb-1.5 block" htmlFor="smtp-username">
              {t("admin.smtpUsername")}
            </Label>
            <Input
              id="smtp-username"
              value={smtpUsername}
              onChange={(event) => setSmtpUsername(event.target.value)}
              autoComplete="off"
            />
          </div>
          <div>
            <Label className="mb-1.5 block" htmlFor="smtp-password">
              {t("admin.smtpPassword")}
            </Label>
            <Input
              id="smtp-password"
              type="password"
              value={smtpPassword}
              onChange={(event) => setSmtpPassword(event.target.value)}
              autoComplete="new-password"
              placeholder={initial.smtp_password_set ? t("admin.smtpPasswordSet") : undefined}
            />
          </div>
          <div>
            <Label className="mb-1.5 block" htmlFor="smtp-sender">
              {t("admin.smtpSender")}
            </Label>
            <Input
              id="smtp-sender"
              value={smtpSender}
              onChange={(event) => setSmtpSender(event.target.value)}
              placeholder="azmark@example.com"
            />
          </div>
          <div className="flex items-end pb-1">
            <CheckboxRow
              id="smtp-starttls"
              label={t("admin.smtpStarttls")}
              checked={smtpStarttls}
              onChange={setSmtpStarttls}
            />
          </div>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="flex-1">
            <Label className="mb-1.5 block" htmlFor="smtp-test-to">
              {t("admin.testEmailTo")}
            </Label>
            <Input
              id="smtp-test-to"
              type="email"
              value={testTo}
              onChange={(event) => setTestTo(event.target.value)}
              placeholder={smtpSender || "you@example.com"}
            />
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={() => sendTest.mutate()}
            disabled={sendTest.isPending || !initial.smtp_host}
          >
            {t("admin.send")}
          </Button>
        </div>
      </section>

      {notice ? (
        <p className={notice.kind === "ok" ? "text-sm text-success" : "text-sm text-danger"}>
          {notice.text}
        </p>
      ) : null}

      <div className="flex justify-end">
        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          {t("common.save")}
        </Button>
      </div>
    </div>
  );
}

export function AdminSettingsCard() {
  const { t } = useI18n();
  const query = useQuery({ queryKey: ["admin-settings"], queryFn: api.getAdminSettings });

  return (
    <Card className="animate-fade-in-up" style={{ animationDelay: "240ms" }}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Settings2 className="h-4 w-4" />
          {t("admin.settings")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 3 }, (_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        ) : query.data ? (
          <SettingsForm initial={query.data} />
        ) : (
          <p className="text-sm text-danger">{t("admin.saveFailed")}</p>
        )}
      </CardContent>
    </Card>
  );
}