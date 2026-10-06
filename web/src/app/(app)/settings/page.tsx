"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";

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
              <Input
                value={profile.timezone}
                onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
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
