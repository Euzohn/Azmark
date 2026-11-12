"use client";

import { useEffect, useRef } from "react";

/*
 * Cloudflare Turnstile widget (spec #60). Loads the official script on
 * demand and renders an explicit widget into the container. The script is
 * shared across the page via a module-level promise so multiple widgets
 * (e.g. login + register) share one download.
 */

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, options: Record<string, unknown>) => string;
      reset: (widgetId?: string) => void;
      remove: (widgetId: string) => void;
    };
    __azmarkTurnstileLoaded?: () => void;
  }
}

const TURNSTILE_SCRIPT =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=__azmarkTurnstileLoaded";

let scriptPromise: Promise<void> | null = null;

function loadTurnstileScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("no browser"));
  if (window.turnstile) return Promise.resolve();
  scriptPromise ??= new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src^="https://challenges.cloudflare.com/turnstile"]`,
    );
    if (existing && existing.dataset.azmarkLoaded) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = TURNSTILE_SCRIPT;
    script.async = true;
    script.dataset.azmarkLoaded = "true";
    script.defer = true;
    window.__azmarkTurnstileLoaded = () => resolve();
    script.onerror = () => {
      scriptPromise = null;
      reject(new Error("failed to load Turnstile"));
    };
    document.head.appendChild(script);
  });
  return scriptPromise;
}

export function TurnstileWidget({
  siteKey,
  onToken,
  onError,
}: {
  siteKey: string;
  onToken: (token: string) => void;
  onError?: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  // Keep the latest callbacks without re-rendering the widget (the script
  // callback only sees the closure captured at render time).
  const onTokenRef = useRef(onToken);
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onTokenRef.current = onToken;
    onErrorRef.current = onError;
  });

  useEffect(() => {
    let cancelled = false;
    loadTurnstileScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.turnstile) return;
        widgetIdRef.current = window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          theme: "auto",
          callback: (token: string) => onTokenRef.current(token),
          "error-callback": () => onErrorRef.current?.(),
        });
      })
      .catch(() => onErrorRef.current?.());
    return () => {
      cancelled = true;
      if (window.turnstile && widgetIdRef.current) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
    };
    // siteKey is fixed per instance settings; callbacks flow through refs,
    // so the widget renders exactly once per site key.
  }, [siteKey]);

  return <div ref={containerRef} />;
}

export function resetTurnstile() {
  if (typeof window !== "undefined" && window.turnstile) {
    window.turnstile.reset();
  }
}