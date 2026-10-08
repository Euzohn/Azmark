"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";

const FALLBACK_TIMEZONES = [
  "UTC",
  "Asia/Shanghai",
  "Asia/Hong_Kong",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Asia/Dubai",
  "Europe/London",
  "Europe/Paris",
  "America/New_York",
  "America/Los_Angeles",
  "Australia/Sydney",
];

function timezoneOptions(): string[] {
  try {
    const zones = Intl.supportedValuesOf("timeZone");
    return zones.length > 0 ? zones : FALLBACK_TIMEZONES;
  } catch {
    return FALLBACK_TIMEZONES;
  }
}

const TIMEZONES = timezoneOptions();

export default function SettingsPage() {
  const { t } = useI18n();
  const { user, setUser } = useAuth();
  const queryClient = useQueryClient();

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

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">{t("settings.title")}</h1>

      <Card>
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
              <Select
                value={profile.timezone}
                onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
              >
                {TIMEZONES.map((zone) => (
                  <option key={zone} value={zone}>
                    {zone}
                  </option>
                ))}
              </Select>
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

      <Card>
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
                  {item.provider === "aerodatabox" ? "AeroDataBox" : item.provider}
                </span>
                {item.configured ? (
                  <span className="text-xs text-primary">{t("settings.providerKeyConfigured")}</span>
                ) : (
                  <span className="text-xs text-muted-foreground">
                    {t("settings.providerKeyNotConfigured")}
                  </span>
                )}
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <Input
                  type="password"
                  autoComplete="off"
                  placeholder={t("settings.providerKeyPlaceholder")}
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
              ) : null}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
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
    </div>
  );
}
