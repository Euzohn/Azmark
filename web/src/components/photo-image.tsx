"use client";

import { ImageOff } from "lucide-react";
import { useState } from "react";

import { photoImageUrl } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface PhotoImageProps {
  id: string;
  alt: string;
  variant?: "full" | "thumb";
  className?: string;
  /** Above-the-fold thumbnails should load eagerly. */
  eager?: boolean;
}

/**
 * Authenticated photo image with a graceful fallback.
 *
 * The session cookie rides along with the request, so a plain `<img>` works;
 * when the blob is missing or storage is down we show a muted placeholder
 * instead of a broken-image icon.
 */
export function PhotoImage({ id, alt, variant = "thumb", className, eager }: PhotoImageProps) {
  const { t } = useI18n();
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        className={cn(
          "flex items-center justify-center bg-muted text-muted-foreground",
          className,
        )}
        role="img"
        aria-label={t("photos.imageUnavailable")}
      >
        <ImageOff className="h-6 w-6" />
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element -- authenticated API blob, not an optimizable static asset
    <img
      src={photoImageUrl(id, variant)}
      alt={alt}
      loading={eager ? "eager" : "lazy"}
      onError={() => setFailed(true)}
      className={className}
    />
  );
}
