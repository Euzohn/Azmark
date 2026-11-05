"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, KeyRound, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CurrencySelect } from "@/components/ui/currency-select";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TimezoneSelect } from "@/components/ui/timezone-select";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";
import type { AccessToken, AccessTokenScope } from "@/lib/types";

const PROVIDER_LABELS: Record<string, string> = {
  aerodatabox: "AeroDataBox",
  aviationstack: "AviationStack",
  variflight: "VariFlight (飞常准)",
  tavily: "Tavily",
  brave: "Brave Search",
  searxng: "SearXNG",
};

type SettingsSection = "profile" | "integrations" | "security";

/**
 * The account page splits the old monolithic settings view across three
 * top-level tabs. Each tab renders one section of this panel, so a single
 * component owns all the hooks/state and the JSX branches on `section`.
 */
export function SettingsPanel({
  embedded = false,
  section = "profile",
}: { embedded?: boolean; section?: SettingsSection } = {}) {
  const { t, locale } = useI18n();
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

  // --- Access tokens (spec #85) -------------------------------------------
  const { data: accessTokens } = useQuery({
    queryKey: ["access-tokens"],
    queryFn: api.listAccessTokens,
  });

  const [tokenForm, setTokenForm] = useState<{
    name: string;
    scope: AccessTokenScope;
    expiresIn: string;
  }>({ name: "", scope: "read", expiresIn: "90" });
  const [tokenError, setTokenError] = useState(false);
  // Plaintext secret only ever lives in this state, never in a query cache.
  const [createdToken, setCreatedToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [deletingToken, setDeletingToken] = useState<AccessToken | null>(null);

  const refreshTokens = () => queryClient.invalidateQueries({ queryKey: ["access-tokens"] });

  const createToken = useMutation({
    mutationFn: () =>
      api.createAccessToken({
        name: tokenForm.name.trim(),
        scope: tokenForm.scope,
        expires_in_days: tokenForm.expiresIn === "never" ? null : Number(tokenForm.expiresIn),
      }),
    onSuccess: (created) => {
      setCreatedToken(created.token);
      setCopied(false);
      setTokenError(false);
      setTokenForm({ name: "", scope: "read", expiresIn: "90" });
      void refreshTokens();
    },
    onError: () => setTokenError(true),
  });

  const revokeToken = useMutation({
    mutationFn: (id: string) => api.revokeAccessToken(id),
    onSuccess: () => void refreshTokens(),
  });

  const deleteToken = useMutation({
    mutationFn: (id: string) => api.deleteAccessToken(id),
    onSuccess: () => {
      setDeletingToken(null);
      void refreshTokens();
    },
  });

  const formatTokenDate = (value: string | null) =>
    value
      ? new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(value))
      : null;

  const copyToken = async () => {
    if (!createdToken) return;
    try {
      await navigator.clipboard.writeText(createdToken);
    } catch {
      // A plain-http deployment is not a secure context, so clipboard API is
      // unavailable; fall back to the legacy selection trick.
      const area = document.createElement("textarea");
      area.value = createdToken;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    setCopied(true);
  };

  return (
    <div className="flex flex-col gap-6">
      {embedded ? null : (
        <h1 className="font-display text-3xl font-semibold tracking-tight animate-fade-in-up">
          {t("settings.title")}
        </h1>
      )}

      {section === "profile" ? (
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
                <CurrencySelect
                  value={profile.currency}
                  onChange={(currency) => setProfile({ ...profile, currency })}
                  allowEmpty={false}
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
      ) : null}

      {section === "integrations" ? (
        <>
          <Card className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
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
        </>
      ) : null}

      {section === "security" ? (
        <>
      <Card className="animate-fade-in-up" style={{ animationDelay: "50ms" }}>
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

      <Card className="animate-fade-in-up" style={{ animationDelay: "225ms" }}>
        <CardHeader>
          <CardTitle>{t("settings.tokens")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          <p className="text-xs text-muted-foreground">{t("settings.tokensHint")}</p>

          <div className="flex flex-col gap-3">
            {accessTokens && accessTokens.items.length > 0 ? (
              accessTokens.items.map((token) => (
                <div
                  key={token.id}
                  className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-border p-4"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium">{token.name}</span>
                      <Badge variant={token.scope === "write" ? "warning" : "neutral"}>
                        {t(
                          token.scope === "write"
                            ? "settings.tokenScopeWrite"
                            : "settings.tokenScopeRead",
                        )}
                      </Badge>
                      {token.revoked_at ? (
                        <Badge variant="danger">{t("settings.tokenRevoked")}</Badge>
                      ) : null}
                    </div>
                    <div className="mt-1.5 font-mono text-xs text-muted-foreground">
                      {token.token_prefix}…
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span>
                        {t("settings.tokenCreatedAt")} · {formatTokenDate(token.created_at)}
                      </span>
                      <span>
                        {t("settings.tokenLastUsed")} ·{" "}
                        {token.last_used_at
                          ? formatTokenDate(token.last_used_at)
                          : t("settings.tokenNeverUsed")}
                      </span>
                      <span>
                        {t("settings.tokenExpires")} ·{" "}
                        {token.expires_at
                          ? formatTokenDate(token.expires_at)
                          : t("settings.tokenNeverExpires")}
                      </span>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {token.revoked_at ? null : (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={revokeToken.isPending}
                        onClick={() => revokeToken.mutate(token.id)}
                      >
                        {t("settings.tokenRevoke")}
                      </Button>
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-danger"
                      onClick={() => setDeletingToken(token)}
                    >
                      {t("settings.tokenDelete")}
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
                {t("settings.tokensEmpty")}
              </p>
            )}
          </div>

          <form
            className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
            onSubmit={(event) => {
              event.preventDefault();
              setTokenError(false);
              createToken.mutate();
            }}
          >
            <div className="lg:col-span-2">
              <Label className="mb-1.5 block">{t("settings.tokenName")}</Label>
              <Input
                value={tokenForm.name}
                onChange={(event) => setTokenForm({ ...tokenForm, name: event.target.value })}
                placeholder={t("settings.tokenNamePlaceholder")}
                maxLength={100}
                required
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.tokenScope")}</Label>
              <Select
                value={tokenForm.scope}
                onChange={(event) =>
                  setTokenForm({ ...tokenForm, scope: event.target.value as AccessTokenScope })
                }
              >
                <option value="read">{t("settings.tokenScopeRead")}</option>
                <option value="write">{t("settings.tokenScopeWrite")}</option>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block">{t("settings.tokenExpiry")}</Label>
              <Select
                value={tokenForm.expiresIn}
                onChange={(event) =>
                  setTokenForm({ ...tokenForm, expiresIn: event.target.value })
                }
              >
                <option value="30">{t("settings.tokenExpiry30")}</option>
                <option value="90">{t("settings.tokenExpiry90")}</option>
                <option value="365">{t("settings.tokenExpiry365")}</option>
                <option value="never">{t("settings.tokenExpiryNever")}</option>
              </Select>
            </div>
            <div className="flex items-center gap-3 lg:col-span-4">
              <Button type="submit" disabled={createToken.isPending}>
                {t(createToken.isPending ? "settings.tokenCreating" : "settings.tokenCreate")}
              </Button>
              {tokenError ? (
                <span className="text-sm text-danger">{t("common.error")}</span>
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

          <div className="flex flex-col gap-3 rounded-lg border border-border p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-medium">{t("settings.exportFirst")}</div>
              <p className="mt-1 text-xs text-muted-foreground">
                {t("settings.exportFirstHint")}
              </p>
            </div>
            <Link href="/account?tab=data" className="shrink-0">
              <Button type="button" variant="outline">
                <Download className="h-4 w-4" />
                {t("settings.exportGoToData")}
              </Button>
            </Link>
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
        </>
      ) : null}

      <Dialog
        open={Boolean(createdToken)}
        onClose={() => {
          setCreatedToken(null);
          setCopied(false);
        }}
        title={t("settings.tokenCreatedTitle")}
        variant="responsive"
      >
        <p className="text-sm text-muted-foreground">{t("settings.tokenCreatedHint")}</p>
        <div className="mt-4 flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3 sm:flex-row sm:items-center">
          <code className="min-w-0 flex-1 select-all break-all font-mono text-xs">
            {createdToken}
          </code>
          <Button type="button" variant="outline" size="sm" onClick={() => void copyToken()}>
            {t(copied ? "settings.tokenCopied" : "settings.tokenCopy")}
          </Button>
        </div>
        <div className="mt-6 flex justify-end">
          <Button
            type="button"
            onClick={() => {
              setCreatedToken(null);
              setCopied(false);
            }}
          >
            {t("common.close")}
          </Button>
        </div>
      </Dialog>

      <Dialog
        open={Boolean(deletingToken)}
        onClose={() => {
          if (!deleteToken.isPending) setDeletingToken(null);
        }}
        title={t("common.confirmDelete")}
        variant="responsive"
      >
        <p className="text-sm text-muted-foreground">{t("settings.tokenDeleteConfirm")}</p>
        {deleteToken.isError ? (
          <p role="alert" className="mt-3 text-sm text-danger">
            {t("common.error")}
          </p>
        ) : null}
        <div className="mt-6 flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={deleteToken.isPending}
            onClick={() => setDeletingToken(null)}
          >
            {t("common.cancel")}
          </Button>
          <Button
            type="button"
            variant="danger"
            disabled={deleteToken.isPending}
            onClick={() => {
              if (deletingToken) deleteToken.mutate(deletingToken.id);
            }}
          >
            {t(deleteToken.isPending ? "common.loading" : "common.delete")}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

/**
 * The standalone /settings route is a legacy entry point — the settings live
 * under /account now. Redirect to the profile tab instead of duplicating the
 * UI. The panel itself is consumed via the named `SettingsPanel` export.
 */
export default function SettingsRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/account?tab=profile");
  }, [router]);
  return null;
}
