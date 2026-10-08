"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BrandMark } from "@/components/brand";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";

export default function RegisterPage() {
  const router = useRouter();
  const { setAuth } = useAuth();
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(false);
    try {
      await api.register(username, password, email || undefined);
      const token = await api.login(username, password);
      useAuth.setState({ token: token.access_token });
      const user = await api.me();
      setAuth(token.access_token, user);
      router.replace("/flights");
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-[100dvh] w-full max-w-sm flex-col justify-center p-6">
      <BrandMark />
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{t("auth.registerTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="flex flex-col gap-4">
            <div>
              <Label className="mb-1.5 block">{t("auth.username")}</Label>
              <Input
                value={username}
                autoComplete="username"
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={3}
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("auth.password")}</Label>
              <Input
                type="password"
                value={password}
                autoComplete="new-password"
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
            <div>
              <Label className="mb-1.5 block">{t("auth.email")}</Label>
              <Input
                type="email"
                value={email}
                autoComplete="email"
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            {error ? <p className="text-sm text-danger">{t("auth.registerFailed")}</p> : null}
            <Button type="submit" disabled={loading}>
              {t("auth.register")}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            {t("auth.hasAccount")}{" "}
            <Link href="/login" className="text-primary hover:underline">
              {t("auth.login")}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
