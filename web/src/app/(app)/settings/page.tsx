"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, KeyRound, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TimezoneSelect } from "@/components/ui/timezone-select";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";

const PROVIDER_LABELS: Record<string, string> = {
  aerodatabox: "AeroDataBox",
  aviationstack: "AviationStack",
  variflight: "VariFlight (飞常准)",
  tavily: "Tavily",
  brave: "Brave Search",
  searxng: "SearXNG",
};

export default function SettingsPage({ embedded = false }: { embedded?: boolean } = {}) {
  const { t } = useI18n();
  const { user, setUser, clear } = useAuth();
  const queryClient = useQueryClient();
  const router = useRouter();

  const [profile, setProfile] = useState({
    display_name: user?.display_name ?? "",
    email: user?.email ?? "",
    timezone: user?.timezone ?? "UTC",
    currency: user?.currency ?? "CNY",
  });
  const [profileSaved, setProfileSaved] = useState(false);

  const updateProfile = useMutation({
    mutationFn: () =>
      api.updateMe({
        display_name: profile.display_name || null,
        email: profile.email || null,
        timezone: profile.timezone,
        currency: profile.currency,
      }),
    onSuccess: (updated) => {
      setUser(updated);
      setProfileSaved(true);
      queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });

  const [newUsername, setNewUsername] = useState("");
  const [usernamePassword, setUsernamePassword] = useState("");
  const [usernameStatus, setUsernameStatus] = useState<"ok" | "error" | null>(null);

  const changeUsername = useMutation({
    mutationFn: () => api.changeUsername(usernamePassword, newUsername),
    onSuccess: (updated) => {
      setUser(updated);
      setNewUsername("");
      setUsernamePassword("");
      setUsernameStatus("ok");
      queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: () => setUsernameStatus("error"),
  });

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordStatus, setPasswordStatus] = useState<"ok" | "error" | null>(null);

  const changePassword = useMutation({
    mutationFn: () => api.changePassword(currentPassword, newPassword),
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setPasswordStatus("ok");
      queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: () => setPasswordStatus("error"),
  });

  const [exportSensitive, setExportSensitive] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(false);

  const downloadExport = async () => {
    setExportError(false);
    setExporting(true);
    try {
      const blob = await api.exportData("json", exportSensitive);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "azmark-export.json";
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      setExportError(true);
    } finally {
      setExporting(false);
    }
  };

  const [confirmUsername, setConfirmUsername] = useState("");
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteError, setDeleteError] = useState<"password" | "lastAdmin" | "failed" | null>(
    null,
  );

  const deleteAccount = useMutation({
    mutationFn: () => api.deleteAccount(deletePassword),
    onSuccess: () => {
      clear();
      router.replace("/login");
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) setDeleteError("lastAdmin");
      else if (error instanceof ApiError && error.status === 400) setDeleteError("password");
      else setDeleteError("failed");
    },
  });

  const { data: providerKeys } = useQuery({
    queryKey: ["provider-keys"],
    queryFn: api.listProviderKeys,
  });

  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});

  const saveKey = useMutation({
    mutationFn: ({ provider, api_key }: { provider: string; api_key: string }) =>
      api.setProviderKey(provider, api_key),
    onSuccess: () => {
      setKeyInputs({});
      queryClient.invalidateQueries({ queryKey: ["provider-keys"] });
    },
  });

  const removeKey = useMutation({
    mutationFn: (provider: string) => api.deleteProviderKey(provider),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["provider-keys"] }),
  });

  const { data: aiSettings } = useQuery({
    queryKey: ["ai-settings"],
    queryFn: api.getAiSettings,
  });

  const [aiForm, setAiForm] = useState({
    provider: "",
    model: "",
    base_url: "",
    api_key: "",
    temperature: "",
    context_limit: "",
  });
  const [aiSaved, setAiSaved] = useState(false);

  const saveAi = useMutation({
    mutationFn: (data: {
      provider: string;
      model: string;
      base_url: string;
      api_key: string;
      temperature: string;
      context_limit: string;
    }) =>
      api.setAiSettings({
        provider: data.provider,
        model: data.model,
        base_url: data.base_url || null,
        api_key: data.api_key || null,
        temperature: data.temperature ? Number(data.temperature) : null,
        context_limit: data.context_limit ? Number(data.context_limit) : null,
      }),
    onSuccess: () => {
      setAiSaved(true);
      setAiForm((prev) => ({ ...prev, api_key: "" }));
      queryClient.invalidateQueries({ queryKey: ["ai-settings"] });
    },
  });

  const removeAi = useMutation({
    mutationFn: () => api.deleteAiSettings(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["ai-settings"] }),
  });

  const AI_PROVIDERS = [
    { value: "openai", label: "OpenAI" },
    { value: "anthropic", label: "Anthropic" },
    { value: "google", label: "Google" },
    { value: "openai_compatible", label: "OpenAI Compatible" },
    { value: "ollama", label: "Ollama" },
    { value: "custom", label: "Custom" },
  ];

  return (
    <div className="flex flex-col gap-6">
      {embedded ? null : (
        <h1 className="font-display text-3xl font-semibold tracking-tight animate-fade-in-up">
          {t("settings.title")}
        </h1>
      )}

      <Card className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
        <CardHeader>
          <CardTitle>{t("settings.profile")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              setProfileSaved(false);
              updateProfile.mutate();
            }}
          >
            <div>
              <Label className="mb-1.5 block">{t("settings.displayName")}</Label>
              <Input
                value={profile.display_name}
                onChange={(e) => setProfile({ ...profile, display_name: e.target.value })}
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.email")}</Label>
              <Input
                type="email"
                value={profile.email}
                onChange={(e) => setProfile({ ...profile, email: e.target.value })}
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.timezone")}</Label>
              <TimezoneSelect
                value={profile.timezone}
                onChange={(timezone) => setProfile({ ...profile, timezone })}
                allowEmpty={false}
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.currency")}</Label>
              <Input
                maxLength={3}
                value={profile.currency}
                onChange={(e) =>
                  setProfile({ ...profile, currency: e.target.value.toUpperCase() })
                }
              />
            </div>
            <div className="flex items-center gap-3 md:col-span-2">
              <Button type="submit" disabled={updateProfile.isPending}>
                {t("common.save")}
              </Button>
              {profileSaved ? (
                <span className="text-sm text-primary">{t("settings.saved")}</span>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="animate-fade-in-up" style={{ animationDelay: "100ms" }}>
        <CardHeader>
          <CardTitle>{t("settings.providerKeys")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-xs text-muted-foreground">{t("settings.providerKeysHint")}</p>
          {providerKeys?.providers.map((item) => (
            <div key={item.provider} className="flex flex-col gap-3 rounded-lg border border-border p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 text-sm font-medium">
                  <KeyRound className="h-4 w-4 text-muted-foreground" />
                  {PROVIDER_LABELS[item.provider] ?? item.provider}
                </span>
                {item.configured ? (
                  <Badge variant="success">{t("settings.providerKeyConfigured")}</Badge>
                ) : (
                  <Badge variant="neutral">{t("settings.providerKeyNotConfigured")}</Badge>
                )}
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <Input
                  type={item.provider === "searxng" ? "text" : "password"}
                  autoComplete="off"
                  placeholder={
                    item.provider === "searxng"
                      ? t("settings.providerKeySearxngPlaceholder")
                      : t("settings.providerKeyPlaceholder")
                  }
                  value={keyInputs[item.provider] ?? ""}
                  onChange={(e) =>
                    setKeyInputs((prev) => ({ ...prev, [item.provider]: e.target.value }))
                  }
                />
                <div className="flex shrink-0 items-center gap-2">
                  <Button
                    size="sm"
                    disabled={saveKey.isPending || !(keyInputs[item.provider] ?? "").trim()}
                    onClick={() =>
                      saveKey.mutate({
                        provider: item.provider,
                        api_key: (keyInputs[item.provider] ?? "").trim(),
                      })
                    }
                  >
                    {t("common.save")}
                  </Button>
                  {item.configured ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => removeKey.mutate(item.provider)}
                      disabled={removeKey.isPending}
                      title={t("common.delete")}
                      aria-label={t("common.delete")}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  ) : null}
                </div>
              </div>
              {item.provider === "aerodatabox" ? (
                <a
                  href="https://rapidapi.com/aerodatabox/api/aerodatabox"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline"
                >
                  {t("settings.providerKeyGetOne")}
                </a>
              ) : item.provider === "aviationstack" ? (
                <a
                  href="https://aviationstack.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline"
                >
                  {t("settings.providerKeyGetAviationStack")}
                </a>
              ) : null}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="animate-fade-in-up" style={{ animationDelay: "150ms" }}>
        <CardHeader>
          <CardTitle>{t("settings.ai")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-xs text-muted-foreground">{t("settings.aiHint")}</p>
          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              setAiSaved(false);
              if (!aiForm.provider || !aiForm.model) return;
              saveAi.mutate(aiForm);
            }}
          >
            <div>
              <Label className="mb-1.5 block">{t("settings.aiProvider")}</Label>
              <Select
                value={aiForm.provider || aiSettings?.provider || ""}
                onChange={(e) => setAiForm({ ...aiForm, provider: e.target.value })}
              >
                <option value="" disabled>
                  —
                </option>
                {AI_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.aiModel")}</Label>
              <Input
                value={aiForm.model || aiSettings?.model || ""}
                onChange={(e) => setAiForm({ ...aiForm, model: e.target.value })}
                placeholder="gpt-4o-mini / llama3 / claude-3-5-sonnet"
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.aiBaseUrl")}</Label>
              <Input
                value={aiForm.base_url || aiSettings?.base_url || ""}
                onChange={(e) => setAiForm({ ...aiForm, base_url: e.target.value })}
                placeholder="https://api.openai.com/v1"
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.aiApiKey")}</Label>
              <Input
                type="password"
                autoComplete="off"
                value={aiForm.api_key}
                onChange={(e) => setAiForm({ ...aiForm, api_key: e.target.value })}
                placeholder={aiSettings?.configured ? t("settings.aiKeyKeep") : ""}
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.aiTemperature")}</Label>
              <Input
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={aiForm.temperature}
                onChange={(e) => setAiForm({ ...aiForm, temperature: e.target.value })}
                placeholder="0.3"
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.aiContextLimit")}</Label>
              <Input
                type="number"
                step="1000"
                min="1000"
                value={aiForm.context_limit}
                onChange={(e) => setAiForm({ ...aiForm, context_limit: e.target.value })}
                placeholder="8000"
              />
            </div>
            <div className="flex items-center gap-3 md:col-span-2">
              <Button type="submit" disabled={saveAi.isPending}>
                {t("common.save")}
              </Button>
              {aiSettings?.configured ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (window.confirm(t("common.delete"))) removeAi.mutate();
                  }}
                  disabled={removeAi.isPending}
                >
                  {t("common.delete")}
                </Button>
              ) : null}
              {aiSettings?.configured ? (
                <span className="text-sm text-primary">{t("settings.aiConfigured")}</span>
              ) : null}
              {aiSaved ? (
                <span className="text-sm text-primary">{t("settings.saved")}</span>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="animate-fade-in-up" style={{ animationDelay: "200ms" }}>
        <CardHeader>
          <CardTitle>{t("settings.security")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-8">
          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              setUsernameStatus(null);
              changeUsername.mutate();
            }}
          >
            <div>
              <Label className="mb-1.5 block">{t("settings.newUsername")}</Label>
              <Input
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                minLength={3}
                required
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.currentPassword")}</Label>
              <Input
                type="password"
                value={usernamePassword}
                onChange={(e) => setUsernamePassword(e.target.value)}
                required
              />
            </div>
            <div className="flex items-center gap-3 md:col-span-2">
              <Button type="submit" variant="outline" disabled={changeUsername.isPending}>
                {t("settings.changeUsername")}
              </Button>
              {usernameStatus === "ok" ? (
                <span className="text-sm text-primary">{t("settings.saved")}</span>
              ) : null}
              {usernameStatus === "error" ? (
                <span className="text-sm text-danger">{t("settings.wrongPassword")}</span>
              ) : null}
            </div>
          </form>

          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              setPasswordStatus(null);
              changePassword.mutate();
            }}
          >
            <div>
              <Label className="mb-1.5 block">{t("settings.currentPassword")}</Label>
              <Input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.newPassword")}</Label>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                minLength={6}
                required
              />
            </div>
            <div className="flex items-center gap-3 md:col-span-2">
              <Button type="submit" variant="outline" disabled={changePassword.isPending}>
                {t("settings.changePassword")}
              </Button>
              {passwordStatus === "ok" ? (
                <span className="text-sm text-primary">{t("settings.saved")}</span>
              ) : null}
              {passwordStatus === "error" ? (
                <span className="text-sm text-danger">{t("settings.wrongPassword")}</span>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>

      <Card
        className="animate-fade-in-up border-danger/40"
        style={{ animationDelay: "250ms" }}
      >
        <CardHeader>
          <CardTitle className="text-danger">{t("settings.dangerZone")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <p className="text-sm text-muted-foreground">{t("settings.dangerZoneHint")}</p>

          <div className="flex flex-col gap-3 rounded-lg border border-border p-4">
            <div>
              <div className="text-sm font-medium">{t("settings.exportFirst")}</div>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("settings.exportFirstHint")}
              </p>
            </div>
            <label className="flex items-start gap-3">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 accent-[var(--color-primary)]"
                checked={exportSensitive}
                onChange={(event) => setExportSensitive(event.target.checked)}
              />
              <span className="text-xs text-muted-foreground">
                {t("data.includeSensitiveHint")}
              </span>
            </label>
            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => void downloadExport()}
                disabled={exporting}
              >
                <Download className="h-4 w-4" />
                {t("settings.exportFirstButton")}
              </Button>
              {exportError ? (
                <span className="text-sm text-danger">{t("common.error")}</span>
              ) : null}
            </div>
          </div>

          <form
            className="flex flex-col gap-3 rounded-lg border border-danger/40 p-4"
            onSubmit={(event) => {
              event.preventDefault();
              setDeleteError(null);
              deleteAccount.mutate();
            }}
          >
            <div>
              <div className="text-sm font-medium">{t("settings.deleteAccount")}</div>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("settings.deleteAccountHint")}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label className="mb-1.5 block">
                  {t("settings.deleteAccountConfirm", { username: user?.username ?? "" })}
                </Label>
                <Input
                  autoComplete="off"
                  value={confirmUsername}
                  onChange={(event) => setConfirmUsername(event.target.value)}
                  required
                />
              </div>
              <div>
                <Label className="mb-1.5 block">{t("settings.currentPassword")}</Label>
                <Input
                  type="password"
                  autoComplete="current-password"
                  value={deletePassword}
                  onChange={(event) => setDeletePassword(event.target.value)}
                  required
                />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="submit"
                variant="danger"
                disabled={
                  deleteAccount.isPending ||
                  !deletePassword ||
                  confirmUsername !== (user?.username ?? "")
                }
              >
                {t("settings.deleteAccountButton")}
              </Button>
              {deleteError === "password" ? (
                <span className="text-sm text-danger">{t("settings.wrongPassword")}</span>
              ) : null}
              {deleteError === "lastAdmin" ? (
                <span className="text-sm text-danger">{t("settings.deleteAccountLastAdmin")}</span>
              ) : null}
              {deleteError === "failed" ? (
                <span className="text-sm text-danger">{t("common.error")}</span>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
