"use client";

import { Plane } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

interface AirlineLogoProps {
  code: string | null;
  className?: string;
}

export function AirlineLogo({ code, className }: AirlineLogoProps) {
  const [errored, setErrored] = useState(false);

  if (!code || errored) {
    return (
      <div
        className={cn(
          "flex shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground",
          className,
        )}
        aria-hidden="true"
      >
        <Plane className="h-1/2 w-1/2" strokeWidth={1.75} />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-border bg-card",
        className,
      )}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- tiny remote logo needs onError fallback; next/image would require remotePatterns config */}
      <img
        src={`https://images.kiwi.com/airlines/64/${code}.png`}
        alt={code}
        loading="lazy"
        onError={() => setErrored(true)}
        className="h-3/5 w-3/5 object-contain"
      />
    </div>
  );
}