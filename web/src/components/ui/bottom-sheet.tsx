"use client";

import { useSyncExternalStore } from "react";
import { Dialog } from "@/components/ui/dialog";
import { useI18n } from "@/lib/i18n";

function subscribe(listener: () => void) {
  const query = window.matchMedia("(max-width: 767px)");
  query.addEventListener("change", listener);
  return () => query.removeEventListener("change", listener);
}

export function BottomSheet({ title, ...props }: Omit<React.ComponentProps<typeof Dialog>, "title"> & { title?: string }) {
  const { t } = useI18n();
  const mobile = useSyncExternalStore(subscribe, () => window.matchMedia("(max-width: 767px)").matches, () => false);
  return mobile ? <Dialog {...props} title={title ?? t("nav.moreTitle")} variant="sheet" /> : null;
}
