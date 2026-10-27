"use client";

import { Dialog } from "@/components/ui/dialog";

export function Modal(props: React.ComponentProps<typeof Dialog>) {
  return <Dialog {...props} variant="modal" />;
}
