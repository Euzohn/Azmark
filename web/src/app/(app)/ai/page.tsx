"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Bot,
  ImagePlus,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/page-header";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { AiProposal } from "@/lib/types";
import { cn } from "@/lib/utils";

const HISTORY_KEY = "azmark-ai-chat-history";
const MAX_IMAGE_DIMENSION = 1920;
const IMAGE_QUALITY = 0.85;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

const QUICK_PROMPT_KEYS = [
  "ai.quick.lookup",
  "ai.quick.stats",
  "ai.quick.add",
  "ai.quick.trip",
  "ai.quick.timeline",
] as const;

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  image?: string;
  proposals?: AiProposal[];
  error?: string;
  streaming?: boolean;
}

let _msgId = 0;
function nextId(): string {
  _msgId += 1;
  return `msg-${_msgId}-${Date.now()}`;
}

function fileToCompressedDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const scale = Math.min(
        1,
        MAX_IMAGE_DIMENSION / Math.max(img.width, img.height),
      );
      const w = Math.round(img.width * scale);
      const h = Math.round(img.height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        reject(new Error("Cannot get canvas context"));
        return;
      }
      ctx.drawImage(img, 0, 0, w, h);
      resolve(canvas.toDataURL("image/jpeg", IMAGE_QUALITY));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to load image"));
    };
    img.src = url;
  });
}

function validateImageFile(file: File): string | null {
  if (file.size > MAX_IMAGE_BYTES) return "tooLarge";
  if (!file.type.startsWith("image/")) return "invalidType";
  return null;
}

function formatDateTime(value: unknown): string {
  try {
    const date = new Date(value as string);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString(undefined, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(value);
  }
}

function formatProposalData(
  data: Record<string, unknown>,
  t: (key: TranslationKey) => string,
): string[] {
  const lines: string[] = [];
  if (data.origin || data.destination) {
    lines.push(`${data.origin ?? "?"} → ${data.destination ?? "?"}`);
  }

  if (data.status === "completed") lines.push(t("ai.proposal.statusCompleted"));
  else if (data.status === "scheduled") lines.push(t("ai.proposal.statusScheduled"));

  if (data.service_number) lines.push(data.service_number as string);
  if (data.train_type) {
    lines.push(`${t("ai.proposal.trainType")}: ${data.train_type}`);
  }
  if (data.departure_time) {
    lines.push(`${t("ai.proposal.departure")}: ${formatDateTime(data.departure_time)}`);
  }
  if (data.arrival_time) {
    lines.push(`${t("ai.proposal.arrival")}: ${formatDateTime(data.arrival_time)}`);
  }
  if (data.carrier) lines.push(data.carrier as string);
  if (data.cabin_class) {
    lines.push(`${t("ai.proposal.cabinClass")}: ${data.cabin_class}`);
  }
  if (data.seat) lines.push(`${t("ai.proposal.seat")}: ${data.seat}`);
  if (data.departure_terminal) {
    lines.push(`${t("ai.proposal.terminal")}: ${data.departure_terminal}`);
  }
  if (data.departure_gate) {
    lines.push(`${t("ai.proposal.gate")}: ${data.departure_gate}`);
  }
  if (data.aircraft_model) {
    lines.push(`${t("ai.proposal.aircraft")}: ${data.aircraft_model}`);
  }
  if (data.distance) {
    lines.push(`${t("ai.proposal.distance")}: ${data.distance} km`);
  }
  if (data.price !== undefined && data.price !== null) {
    const currency = data.currency ? ` ${data.currency}` : "";
    lines.push(`${t("ai.proposal.price")}: ${data.price}${currency}`);
  }
  if (data.notes) lines.push(data.notes as string);
  return lines;
}

function loadHistory(): ChatMessage[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as ChatMessage[];
  } catch {
    return [];
  }
}

function saveHistory(messages: ChatMessage[]) {
  try {
    const serializable = messages.map((m) => ({
      ...m,
      image: undefined,
      streaming: undefined,
    }));
    localStorage.setItem(HISTORY_KEY, JSON.stringify(serializable));
  } catch {
    // localStorage quota exceeded
  }
}

export default function AiChatPage() {
  const { t } = useI18n();
  const { token } = useAuth();
  const queryClient = useQueryClient();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data: aiSettings } = useQuery({
    queryKey: ["ai-settings"],
    queryFn: api.getAiSettings,
    enabled: !!token,
  });
  const configured = aiSettings?.configured ?? false;

  useEffect(() => {
    setMessages(loadHistory());
  }, []);

  useEffect(() => {
    saveHistory(messages);
  }, [messages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, streaming]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [input]);

  const handleImageFile = useCallback(
    async (file: File) => {
      setImageError(null);
      const error = validateImageFile(file);
      if (error) {
        setImageError(
          error === "tooLarge" ? t("ai.imageTooLarge") : t("ai.invalidType"),
        );
        return;
      }
      try {
        const dataUrl = await fileToCompressedDataUrl(file);
        setImagePreview(dataUrl);
      } catch {
        setImageError(t("ai.imageError"));
      }
    },
    [t],
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) {
            e.preventDefault();
            void handleImageFile(file);
            return;
          }
        }
      }
    },
    [handleImageFile],
  );

  const handleSend = useCallback(
    async (text?: string) => {
      const messageText = (text ?? input).trim();
      if (!messageText && !imagePreview) return;
      if (streaming) return;

      const finalText = messageText || t("ai.defaultImagePrompt");

      const userMsg: ChatMessage = {
        id: nextId(),
        role: "user",
        content: finalText,
        image: imagePreview ?? undefined,
      };

      const assistantId = nextId();
      setMessages((prev) => [
        ...prev,
        userMsg,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          streaming: true,
        },
      ]);
      setInput("");
      setImagePreview(null);
      setStreaming(true);

      try {
        let proposals: AiProposal[] = [];

        for await (const event of api.chatAiStream(finalText, imagePreview)) {
          if (event.type === "text" && event.content) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + event.content }
                  : m,
              ),
            );
          } else if (event.type === "proposals" && event.proposals) {
            proposals = event.proposals.map((p) => ({
              ...p,
              status: "pending" as const,
            }));
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, proposals } : m,
              ),
            );
          } else if (event.type === "error") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      error: event.message ?? t("ai.error"),
                      streaming: false,
                    }
                  : m,
              ),
            );
          } else if (event.type === "done") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, streaming: false } : m,
              ),
            );
          }
        }

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, streaming: false } : m,
          ),
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 400) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    error: err.message,
                    streaming: false,
                  }
                : m,
            ),
          );
        } else {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    error:
                      err instanceof Error
                        ? err.message
                        : t("ai.error"),
                    streaming: false,
                  }
                : m,
            ),
          );
        }
      } finally {
        setStreaming(false);
      }
    },
    [input, imagePreview, streaming, t],
  );

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["flights"] });
    queryClient.invalidateQueries({ queryKey: ["trains"] });
    queryClient.invalidateQueries({ queryKey: ["transports"] });
    queryClient.invalidateQueries({ queryKey: ["timeline"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["statistics"] });
  };

  const confirmCreate = useMutation({
    mutationFn: async (proposal: AiProposal) => {
      const data = proposal.data as Record<string, unknown>;
      if (proposal.record_type === "flight") {
        return api.createFlight(data);
      }
      if (proposal.record_type === "train") {
        return api.createTrain(data);
      }
      return api.createOtherTransport(data);
    },
    onSuccess: () => invalidateAll(),
  });

  const confirmDelete = useMutation({
    mutationFn: async (proposal: AiProposal) => {
      const id = (proposal.data as Record<string, unknown>)
        .record_id as string;
      if (proposal.record_type === "flight") return api.deleteFlight(id);
      if (proposal.record_type === "train") return api.deleteTrain(id);
      return api.deleteOtherTransport(id);
    },
    onSuccess: () => invalidateAll(),
  });

  const handleConfirm = (messageId: string, proposal: AiProposal) => {
    if (proposal.action === "delete_transport") {
      if (!window.confirm(t("ai.deleteConfirm"))) return;
      confirmDelete.mutate(proposal, {
        onSuccess: () => markProposal(messageId, proposal.id, "saved"),
      });
    } else {
      confirmCreate.mutate(proposal, {
        onSuccess: () => markProposal(messageId, proposal.id, "saved"),
      });
    }
  };

  const markProposal = (
    messageId: string,
    proposalId: string,
    status: "saved" | "cancelled",
  ) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === messageId
          ? {
              ...msg,
              proposals: msg.proposals?.map((p) =>
                p.id === proposalId ? { ...p, status } : p,
              ),
            }
          : msg,
      ),
    );
  };

  const clearHistory = () => {
    setMessages([]);
    localStorage.removeItem(HISTORY_KEY);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Skip when an IME is mid-composition (e.g. typing English under a Chinese
    // input method): Enter then confirms the candidate, it must not send.
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="flex h-[calc(100dvh-8rem)] flex-col gap-4 md:h-[calc(100dvh-4rem)]">
      <PageHeader
        title={t("ai.title")}
        actions={
          messages.length > 0 ? (
            <Button
              variant="ghost"
              size="icon"
              onClick={clearHistory}
              title={t("ai.clearHistory")}
              aria-label={t("ai.clearHistory")}
              className="h-9 w-9 text-muted-foreground hover:text-danger"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          ) : null
        }
      />

      {!configured ? (
        <EmptyState
          icon={Sparkles}
          title={t("ai.notConfigured")}
          hint={t("ai.notConfiguredHint")}
          action={
            <Link href="/account?tab=profile">
              <Button variant="outline">{t("ai.goToSettings")}</Button>
            </Link>
          }
        />
      ) : (
        <>
          <div
            ref={scrollRef}
            onPaste={handlePaste}
            className="flex flex-1 flex-col gap-4 overflow-y-auto rounded-2xl border border-border bg-card/50 p-4"
          >
            {messages.length === 0 ? (
              <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-4 text-center">
                <Bot className="h-10 w-10 text-muted-foreground" strokeWidth={1.5} />
                <div>
                  <p className="font-display text-lg font-medium">{t("ai.empty")}</p>
                  <p className="mx-auto max-w-md text-sm text-muted-foreground">
                    {t("ai.emptyHint")}
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  {QUICK_PROMPT_KEYS.map((key) => (
                    <Button
                      key={key}
                      variant="outline"
                      size="sm"
                      onClick={() => void handleSend(t(key))}
                      className="text-xs"
                    >
                      {t(key)}
                    </Button>
                  ))}
                </div>
              </div>
            ) : null}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={cn(
                  "mx-auto flex w-full max-w-3xl animate-fade-in-up",
                  msg.role === "user" ? "justify-end" : "justify-start",
                )}
              >
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm",
                    msg.role === "user"
                      ? "bg-gradient-to-br from-[#e0a737] to-[#b45309] text-primary-foreground"
                      : msg.error
                        ? "bg-danger/10 text-danger"
                        : "bg-accent text-accent-foreground",
                  )}
                >
                  {msg.role === "user" && msg.image ? (
                    <ChatImage src={msg.image} className="mb-2 max-h-48 w-auto rounded-lg" />
                  ) : null}

                  {msg.role === "assistant" && msg.streaming && !msg.content ? (
                    <div className="flex items-center gap-1 py-1">
                      <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" />
                    </div>
                  ) : msg.error ? (
                    <p className="whitespace-pre-wrap">{msg.error}</p>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}

                  {msg.proposals && msg.proposals.length > 0 ? (
                    <div className="mt-3 flex flex-col gap-2">
                      {msg.proposals.map((proposal) => (
                        <ProposalCard
                          key={proposal.id}
                          proposal={proposal}
                          onSave={() => handleConfirm(msg.id, proposal)}
                          onCancel={() => markProposal(msg.id, proposal.id, "cancelled")}
                          saving={
                            confirmCreate.isPending || confirmDelete.isPending
                          }
                        />
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          <div className="mx-auto flex w-full max-w-3xl flex-col gap-2">
            {imagePreview && (
              <div className="relative inline-flex items-center gap-2 self-start">
                <ChatImage src={imagePreview} className="h-16 w-16 rounded-lg border border-border object-cover" />
                <button
                  type="button"
                  onClick={() => setImagePreview(null)}
                  className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-background text-xs text-muted-foreground shadow-sm transition-colors hover:bg-destructive hover:text-white"
                  aria-label={t("ai.removeImage")}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}

            {imageError && (
              <p className="text-xs text-danger">{imageError}</p>
            )}

            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleImageFile(file);
                  e.target.value = "";
                }}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => fileInputRef.current?.click()}
                disabled={streaming}
                title={t("ai.attachHint")}
                aria-label={t("ai.attachHint")}
                className="h-10 w-10 text-muted-foreground hover:text-foreground"
              >
                <ImagePlus className="h-5 w-5" />
              </Button>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                onPaste={handlePaste}
                placeholder={t("ai.placeholder")}
                disabled={streaming}
                rows={1}
                className="min-h-10 flex-1 resize-none rounded-xl border border-border bg-card px-3.5 py-2 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-muted-foreground/80 focus:border-primary/50 focus:ring-2 focus:ring-ring/25 disabled:opacity-50"
              />
              <Button
                type="button"
                size="icon"
                onClick={() => void handleSend()}
                disabled={streaming || (!input.trim() && !imagePreview)}
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function ChatImage({
  src,
  className,
}: {
  src: string;
  className?: string;
}) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt="" className={className} />
  );
}

function ProposalCard({
  proposal,
  onSave,
  onCancel,
  saving,
}: {
  proposal: AiProposal & { status?: "pending" | "saved" | "cancelled" };
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const { t } = useI18n();
  const isDelete = proposal.action === "delete_transport";
  const saved = proposal.status === "saved";
  const cancelled = proposal.status === "cancelled";
  const dataLines = isDelete ? [] : formatProposalData(proposal.data, t);

  if (saved || cancelled) {
    return (
      <div className="rounded-lg border border-border bg-background px-3 py-2 text-xs">
        <span className="font-medium">
          {saved ? t("ai.saved") : t("ai.cancelled")}
        </span>
        <span className="ml-2 text-muted-foreground">{proposal.summary}</span>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-background px-3 py-2.5">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-medium">
        {isDelete ? (
          <Trash2 className="h-3.5 w-3.5 text-danger" />
        ) : (
          <Sparkles className="h-3.5 w-3.5 text-primary" />
        )}
        <span>
          {isDelete ? t("ai.proposal.delete") : t("ai.proposal.create")}{" "}
          {proposal.record_type}
        </span>
      </div>
      <p className="mb-1 text-sm text-muted-foreground">{proposal.summary}</p>
      {dataLines.length > 0 ? (
        <ul className="mb-2 list-inside list-disc text-xs text-muted-foreground">
          {dataLines.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      ) : null}
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant={isDelete ? "danger" : "default"}
          onClick={onSave}
          disabled={saving}
        >
          {t("ai.save")}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>
          {t("ai.cancel")}
        </Button>
      </div>
    </div>
  );
}
