"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/brand";
import { TurnstileWidget, resetTurnstile } from "@/components/turnstile";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n } from "@/lib/i18n";
import { usePageTitle } from "@/lib/page-title";
import type { AuthConfig, CaptchaChallenge } from "@/lib/types";

export default function RegisterPage() {
  const router = useRouter();
  const { setUser } = useAuth();
  const { t } = useI18n();
  usePageTitle(t("auth.register"));
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [captchaAnswer, setCaptchaAnswer] = useState("");
  const [turnstileToken, setTurnstileToken] = useState("");
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [challenge, setChallenge] = useState<CaptchaChallenge | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [closed, setClosed] = useState(false);
  const [loading, setLoading] = useState(false);

  const turnstileActive =
    config?.registration_captcha_enabled === true &&
    config.captcha_provider === "turnstile" &&
    Boolean(config.turnstile_site_key);

  useEffect(() => {
    let cancelled = false;
    api
      .getAuthConfig()
      .then((next) => {
        if (cancelled) return;
        setConfig(next);
        setClosed(!next.allow_registration);
        const turnstile = next.registration_captcha_enabled &&
          next.captcha_provider === "turnstile" &&
          Boolean(next.turnstile_site_key);
        if (next.registration_captcha_enabled && !turnstile) {
          api
            .getCaptcha()
            .then((fresh) => {
              if (!cancelled) setChallenge(fresh);
            })
            .catch(() => {});
        }
      })
      .catch(() => {
        // The config endpoint is only a hint; the server enforces the real
        // rule on submit, so fall back to the open form on a transient error.
        if (!cancelled) {
          setConfig({ allow_registration: true, registration_captcha_enabled: false, captcha_provider: "arithmetic", turnstile_site_key: null });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshChallenge = () => {
    setCaptchaAnswer("");
    api
      .getCaptcha()
      .then(setChallenge)
      .catch(() => setChallenge(null));
  };

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.register({
        username,
        password,
        email: email || undefined,
        captcha_token: turnstileActive ? turnstileToken : challenge?.token,
        captcha_answer: turnstileActive ? undefined : challenge ? captchaAnswer : undefined,
      });
      await api.login(username, password);
      // Login delivered the session as an HttpOnly cookie (spec #4.3); fetch
      // the profile through it and persist only the user record.
      const user = await api.me();
      setUser(user);
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setClosed(true);
      } else if (err instanceof ApiError && err.status === 400) {
        setError(t("auth.captchaFailed"));
        if (turnstileActive) {
          setTurnstileToken("");
          resetTurnstile();
        } else {
          refreshChallenge();
        }
      } else {
        setError(t("auth.registerFailed"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-glow mx-auto flex min-h-[100dvh] w-full max-w-sm flex-col justify-center p-6">
      <BrandMark className="animate-fade-in-up" />
      <Card className="animate-fade-in-up" style={{ animationDelay: "100ms" }}>
        <CardHeader>
          <CardTitle className="text-lg">
            {closed ? t("auth.registerClosedTitle") : t("auth.registerTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {config === null ? (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : closed ? (
            <p className="text-sm leading-relaxed text-muted-foreground">
              {t("auth.registerClosedHint")}
            </p>
          ) : (
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
              {turnstileActive && config?.turnstile_site_key ? (
                <TurnstileWidget
                  siteKey={config.turnstile_site_key}
                  onToken={setTurnstileToken}
                />
              ) : null}
              {config.registration_captcha_enabled && !turnstileActive && challenge ? (
                <div>
                  <Label className="mb-1.5 block">
                    {t("auth.captcha", { question: challenge.question })}
                  </Label>
                  <Input
                    value={captchaAnswer}
                    onChange={(e) => setCaptchaAnswer(e.target.value)}
                    placeholder={t("auth.captchaPlaceholder")}
                    autoComplete="off"
                    inputMode="numeric"
                    required
                  />
                </div>
              ) : null}
              {error ? <p className="text-sm text-danger">{error}</p> : null}
              <Button type="submit" disabled={loading}>
                {t("auth.register")}
              </Button>
            </form>
          )}
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