"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AlertTriangle,
  Bot,
  ChevronRight,
  ImagePlus,
  PanelLeftOpen,
  Plus,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { EmptyState } from "@/components/ui/empty-state";
import { Markdown } from "@/components/markdown";
import { PageHeader } from "@/components/page-header";
import { api, ApiError } from "@/lib/api";
import { buildChatHistory } from "@/lib/ai-history";
import {
  activeConversation,
  appendMessage,
  createConversation,
  loadStore,
  patchMessage,
  removeConversation,
  saveStore,
  sortByUpdated,
  upsertConversation,
  type Conversation,
  type ConversationStore,
  type StoredMessage,
} from "@/lib/ai-conversations";
import { useAuth } from "@/lib/auth-store";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import { formatZonedDateTime } from "@/lib/datetime";
import { uuid } from "@/lib/uuid";
import type {
  ActivityInput,
  AiProposal,
  ExpenseInput,
  FlightInput,
  HotelInput,
  NoteInput,
  OtherTransportInput,
  PlaceInput,
  TrainInput,
  TripInput,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_IMAGE_DIMENSION = 1920;
const IMAGE_QUALITY = 0.85;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

const QUICK_PROMPT_KEYS = [
  "ai.quick.lookup",
  "ai.quick.stats",
  "ai.quick.add",
  "ai.quick.trip",
  "ai.quick.timeline",
  "ai.quick.journal",
] as const;

/** A rendered turn. Images and streaming state are tracked separately (not persisted). */
type ChatMessage = StoredMessage;

/** Collapsible chain-of-thought block shown above an assistant reply. */
function ReasoningBlock({
  text,
  streaming,
  label,
}: {
  text: string;
  streaming: boolean;
  label: string;
}) {
  const [open, setOpen] = useState(streaming);
  return (
    <div className="mb-2 overflow-hidden rounded-lg border border-border/60 bg-background/40">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-1.5 px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
        aria-expanded={open}
      >
        <ChevronRight
          className={cn("h-3.5 w-3.5 shrink-0 transition-transform", open && "rotate-90")}
        />
        <span>{label}</span>
        {streaming ? <span className="animate-pulse">…</span> : null}
      </button>
      {open ? (
        <div className="max-h-64 overflow-y-auto whitespace-pre-wrap border-t border-border/60 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          {text}
        </div>
      ) : null}
    </div>
  );
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

function formatProposalData(
  proposal: AiProposal,
  t: (key: TranslationKey) => string,
  locale: string,
): string[] {
  const data = proposal.data as Record<string, unknown>;
  const lines: string[] = [];

  // Transport proposals (flight/train/other) carry origin/destination times etc.
  if (!["trip", "hotel", "expense", "note", "place", "activity"].includes(proposal.record_type)) {
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
      lines.push(
        `${t("ai.proposal.departure")}: ${formatZonedDateTime(
          String(data.departure_time),
          locale,
          data.departure_timezone as string | null,
        )}`,
      );
    }
    if (data.arrival_time) {
      lines.push(
        `${t("ai.proposal.arrival")}: ${formatZonedDateTime(
          String(data.arrival_time),
          locale,
          data.arrival_timezone as string | null,
        )}`,
      );
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

  if (proposal.action === "add_place_to_trip") {
    // The summary already names the trip and place; nothing extra to show.
    return lines;
  }

  switch (proposal.record_type) {
    case "trip": {
      if (data.name) lines.push(data.name as string);
      if (data.start_date) {
        const range = data.end_date
          ? `${data.start_date} → ${data.end_date}`
          : String(data.start_date);
        lines.push(`${t("ai.proposal.tripDates")}: ${range}`);
      }
      if (data.origin && data.destination) {
        lines.push(`${data.origin} → ${data.destination}`);
      } else if (data.destination) {
        lines.push(data.destination as string);
      }
      if (data.description) lines.push(data.description as string);
      if (data.status) lines.push(String(data.status));
      return lines;
    }
    case "hotel": {
      if (data.hotel) lines.push(data.hotel as string);
      if (data.check_in) {
        const range = data.check_out
          ? `${data.check_in} → ${data.check_out}`
          : String(data.check_in);
        lines.push(`${t("ai.proposal.hotelDates")}: ${range}`);
      }
      if (data.status === "completed") lines.push(t("ai.proposal.statusCompleted"));
      else if (data.status === "scheduled") lines.push(t("ai.proposal.statusScheduled"));
      if (data.room_type) lines.push(`${t("ai.proposal.roomType")}: ${data.room_type}`);
      if (data.room_number) lines.push(`${t("ai.proposal.roomNumber")}: ${data.room_number}`);
      if (data.address) lines.push(`${t("ai.proposal.hotelAddress")}: ${data.address}`);
      if (data.price !== undefined && data.price !== null) {
        const currency = data.currency ? ` ${data.currency}` : "";
        lines.push(`${t("ai.proposal.price")}: ${data.price}${currency}`);
      }
      if (data.notes) lines.push(data.notes as string);
      return lines;
    }
    case "expense": {
      if (data.category) lines.push(`${t("ai.proposal.category")}: ${data.category}`);
      if (data.amount !== undefined && data.amount !== null) {
        const currency = data.currency ? ` ${data.currency}` : "";
        lines.push(`${t("ai.proposal.amount")}: ${data.amount}${currency}`);
      }
      if (data.occurred_at) {
        lines.push(
          `${t("expenses.occurredAt")}: ${formatZonedDateTime(
            String(data.occurred_at),
            locale,
            null,
          )}`,
        );
      }
      if (data.description) lines.push(data.description as string);
      return lines;
    }
    case "note": {
      if (data.title) lines.push(`${t("notes.noteTitle")}: ${data.title}`);
      if (data.content) lines.push(`${t("notes.content")}: ${data.content}`);
      return lines;
    }
    case "place": {
      if (data.name) lines.push(data.name as string);
      if (data.localized_name) lines.push(data.localized_name as string);
      if (data.type) lines.push(`${t("places.type")}: ${data.type}`);
      const location = [data.city, data.region, data.country].filter(Boolean).join(" · ");
      if (location) lines.push(`${t("ai.proposal.location")}: ${location}`);
      if (data.lat !== undefined && data.lat !== null && data.lon !== undefined && data.lon !== null) {
        lines.push(`${t("ai.proposal.coordinates")}: ${data.lat}, ${data.lon}`);
      }
      return lines;
    }
    case "activity": {
      if (data.name) lines.push(data.name as string);
      if (data.type) lines.push(`${t("activities.type")}: ${data.type}`);
      if (data.start_at) {
        lines.push(
          `${t("activities.startAt")}: ${formatZonedDateTime(String(data.start_at), locale, null)}`,
        );
      }
      if (data.end_at) {
        lines.push(
          `${t("activities.endAt")}: ${formatZonedDateTime(String(data.end_at), locale, null)}`,
        );
      }
      if (data.price !== undefined && data.price !== null) {
        const currency = data.currency ? ` ${data.currency}` : "";
        lines.push(`${t("ai.proposal.price")}: ${data.price}${currency}`);
      }
      if (data.notes) lines.push(data.notes as string);
      return lines;
    }
    default:
      return lines;
  }
}


export default function AiChatPage() {
  const { t } = useI18n();
  const { token } = useAuth();
  const queryClient = useQueryClient();

  const [store, setStore] = useState<ConversationStore>(() => loadStore());
  // A trip page can deep-link here with a prefilled request, e.g.
  // /ai?q=<journal prompt>. Guarded like the wrapped page: the shell renders
  // after auth hydration, so this never runs on the server.
  const [input, setInput] = useState(() => {
    if (typeof window === "undefined") return "";
    return new URLSearchParams(window.location.search).get("q") ?? "";
  });
  // Consume the one-shot deep-link prompt so a refresh does not refill input.
  useEffect(() => {
    if (window.location.search.includes("q=")) {
      const url = new URL(window.location.href);
      url.searchParams.delete("q");
      window.history.replaceState(null, "", url.toString());
    }
  }, []);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [conversationsOpen, setConversationsOpen] = useState(false);

  // Message images (data URLs) live outside the persisted store to keep
  // localStorage small; they are per-session and intentionally not durable.
  const [messageImages, setMessageImages] = useState<Record<string, string>>({});

  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data: aiSettings } = useQuery({
    queryKey: ["ai-settings"],
    queryFn: api.getAiSettings,
    enabled: !!token,
  });
  const configured = aiSettings?.configured ?? false;

  // The store is loaded lazily (see useState initializer) — safe because the
  // AppShell only renders children after auth hydration, so this never runs on
  // the server. Persist every change straight back to localStorage.
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [store, streamingId]);

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

  const current = activeConversation(store);
  const messages: ChatMessage[] = useMemo(() => current?.messages ?? [], [current]);

  // Functional updates read the latest store, so streaming patches accumulate
  // correctly even though the async send loop captures these callbacks once.
  const commit = useCallback((updater: (prev: ConversationStore) => ConversationStore) => {
    setStore(updater);
  }, []);

  // Persist on every change. The store is loaded lazily in the useState
  // initializer, so the first run simply rewrites the loaded value.
  useEffect(() => {
    saveStore(store);
  }, [store]);

  const updateActive = useCallback(
    (fn: (conv: Conversation) => Conversation) => {
      commit((prev) => ({
        ...prev,
        conversations: prev.conversations.map((c) =>
          c.id === prev.activeId ? fn(c) : c,
        ),
      }));
    },
    [commit],
  );

  /** Start a fresh chat; reuses the active one if it is still empty. */
  const newChat = useCallback(() => {
    const active = current;
    if (active && active.messages.length === 0) {
      setConversationsOpen(false);
      return;
    }
    const fresh = createConversation();
    commit((prev) => ({ ...upsertConversation(prev, fresh), activeId: fresh.id }));
    setConversationsOpen(false);
  }, [commit, current]);

  const selectConversation = useCallback(
    (id: string) => {
      commit((prev) => (id !== prev.activeId ? { ...prev, activeId: id } : prev));
      setConversationsOpen(false);
    },
    [commit],
  );

  const deleteConversation = useCallback(
    (id: string) => {
      // Deleting a conversation is irreversible (localStorage only), so both
      // the header trash and the per-item trash confirm here.
      if (!window.confirm(t("common.confirmDelete"))) return;
      commit((prev) => removeConversation(prev, id));
    },
    [commit, t],
  );

  const markProposal = useCallback(
    (
      messageId: string,
      proposalId: string,
      status: "saved" | "cancelled" | "duplicate",
      existingRecordId?: string,
    ) => {
      updateActive((conv) =>
        patchMessage(conv, messageId, {
          proposals: conv.messages
            .find((m) => m.id === messageId)
            ?.proposals?.map((p) =>
              p.id === proposalId ? { ...p, status, existingRecordId } : p,
            ),
        }),
      );
    },
    [updateActive],
  );

  const handleSend = useCallback(
    async (text?: string) => {
      const messageText = (text ?? input).trim();
      if (!messageText && !imagePreview) return;
      if (streamingId) return;

      const finalText = messageText || t("ai.defaultImagePrompt");
      const image = imagePreview ?? undefined;

      // Prior turns (with proposal outcomes) give the stateless backend enough
      // context to follow up without re-proposing what the user already saved.
      const history = buildChatHistory(messages);

      const userMsg: ChatMessage = {
        id: uuid(),
        role: "user",
        content: finalText,
      };

      const assistantId = uuid();
      // Seed the conversation from the active one, or open a brand-new chat
      // when the user is sending into an empty page. Functional so it builds
      // on the latest store even if another render happened since the callback
      // was created.
      commit((prev) => {
        const base =
          prev.conversations.find((c) => c.id === prev.activeId) ?? createConversation();
        const withUser = appendMessage(base, userMsg);
        const withAssistant = appendMessage(withUser, {
          id: assistantId,
          role: "assistant",
          content: "",
        });
        return {
          ...upsertConversation(prev, withAssistant),
          activeId: withAssistant.id,
        };
      });
      if (image) setMessageImages((prev) => ({ ...prev, [userMsg.id]: image }));
      setInput("");
      setImagePreview(null);
      setStreamingId(assistantId);

      try {
        let proposals: AiProposal[] = [];

        for await (const event of api.chatAiStream(finalText, image, history)) {
          if (event.type === "reasoning" && event.content) {
            updateActive((conv) =>
              patchMessage(conv, assistantId, {
                reasoning:
                  (conv.messages.find((m) => m.id === assistantId)?.reasoning ?? "") +
                  event.content,
              }),
            );
          } else if (event.type === "text" && event.content) {
            updateActive((conv) =>
              patchMessage(conv, assistantId, {
                content: (conv.messages.find((m) => m.id === assistantId)?.content ?? "") + event.content,
              }),
            );
          } else if (event.type === "proposals" && event.proposals) {
            proposals = event.proposals.map((p) => ({
              ...p,
              status: "pending" as const,
            }));
            updateActive((conv) => patchMessage(conv, assistantId, { proposals }));
          } else if (event.type === "error") {
            updateActive((conv) =>
              patchMessage(conv, assistantId, {
                error: event.message ?? t("ai.error"),
              }),
            );
          }
        }
      } catch (err) {
        const message =
          err instanceof ApiError && err.status === 400
            ? err.message
            : err instanceof Error
              ? err.message
              : t("ai.error");
        updateActive((conv) => patchMessage(conv, assistantId, { error: message }));
      } finally {
        setStreamingId(null);
      }
    },
    [
      commit,
      imagePreview,
      input,
      messages,
      streamingId,
      t,
      updateActive,
    ],
  );

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["flights"] });
    queryClient.invalidateQueries({ queryKey: ["trains"] });
    queryClient.invalidateQueries({ queryKey: ["transports"] });
    queryClient.invalidateQueries({ queryKey: ["hotels"] });
    queryClient.invalidateQueries({ queryKey: ["trips"] });
    queryClient.invalidateQueries({ queryKey: ["expenses"] });
    queryClient.invalidateQueries({ queryKey: ["notes"] });
    queryClient.invalidateQueries({ queryKey: ["places"] });
    queryClient.invalidateQueries({ queryKey: ["activities"] });
    queryClient.invalidateQueries({ queryKey: ["timeline"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["statistics"] });
  };

  const confirmWrite = useMutation({
    mutationFn: async ({
      proposal,
      force,
    }: {
      proposal: AiProposal;
      force: boolean;
    }) => {
      const data = proposal.data as Record<string, unknown>;
      const isUpdate = proposal.action.startsWith("update");
      const id = String(data.record_id ?? "");
      const fields = Object.fromEntries(
        Object.entries(data).filter(([key]) => key !== "record_id"),
      );

      if (isUpdate) {
        if (proposal.record_type === "flight") {
          return api.updateFlight(id, fields as unknown as FlightInput);
        }
        if (proposal.record_type === "train") {
          return api.updateTrain(id, fields as unknown as TrainInput);
        }
        if (proposal.record_type === "hotel") {
          return api.updateHotel(id, fields as unknown as HotelInput);
        }
        if (proposal.record_type === "trip") {
          return api.updateTrip(id, fields as unknown as Partial<TripInput>);
        }
        if (proposal.record_type === "expense") {
          return api.updateExpense(id, fields as unknown as ExpenseInput);
        }
        if (proposal.record_type === "note") {
          return api.updateNote(id, fields as unknown as NoteInput);
        }
        if (proposal.record_type === "place") {
          return api.updatePlace(id, fields as unknown as PlaceInput);
        }
        if (proposal.record_type === "activity") {
          return api.updateActivity(id, fields as unknown as ActivityInput);
        }
        return api.updateOtherTransport(
          id,
          fields as unknown as OtherTransportInput,
        );
      }

      // A place has no trip_id of its own; joining a trip is a separate call.
      if (proposal.action === "add_place_to_trip") {
        return api.addTripItem(
          String(data.trip_id),
          {
            item_type: "place",
            item_id: String(data.place_id),
            start_at: (data.start_at as string | null) ?? null,
            end_at: (data.end_at as string | null) ?? null,
          },
          proposal.id,
        );
      }

      if (proposal.record_type === "flight") {
        return api.createFlight(data, force);
      }
      if (proposal.record_type === "train") {
        return api.createTrain(data, force);
      }
      if (proposal.record_type === "hotel") {
        return api.createHotel(data, force);
      }
      if (proposal.record_type === "trip") {
        return api.createTrip(data as unknown as TripInput);
      }
      if (proposal.record_type === "expense") {
        // A retried save must not create a second spend (docs §6.5).
        return api.createExpense(data as unknown as ExpenseInput, proposal.id);
      }
      if (proposal.record_type === "note") {
        return api.createNote(data as unknown as NoteInput);
      }
      if (proposal.record_type === "place") {
        return api.createPlace(data as unknown as PlaceInput);
      }
      if (proposal.record_type === "activity") {
        return api.createActivity(data as unknown as ActivityInput, proposal.id);
      }
      return api.createOtherTransport(data, force);
    },
    onSuccess: () => invalidateAll(),
  });

  const confirmDelete = useMutation({
    mutationFn: async (proposal: AiProposal) => {
      const id = (proposal.data as Record<string, unknown>).record_id as string;
      if (proposal.record_type === "trip") return api.deleteTrip(id);
      if (proposal.record_type === "hotel") return api.deleteHotel(id);
      if (proposal.record_type === "flight") return api.deleteFlight(id);
      if (proposal.record_type === "train") return api.deleteTrain(id);
      if (proposal.record_type === "expense") return api.deleteExpense(id);
      if (proposal.record_type === "note") return api.deleteNote(id);
      if (proposal.record_type === "place") return api.deletePlace(id);
      if (proposal.record_type === "activity") return api.deleteActivity(id);
      return api.deleteOtherTransport(id);
    },
    onSuccess: () => invalidateAll(),
  });

  const handleConfirm = (messageId: string, proposal: AiProposal) => {
    if (proposal.action.startsWith("delete")) {
      if (!window.confirm(t("ai.deleteConfirm"))) return;
      confirmDelete.mutate(proposal, {
        onSuccess: () => markProposal(messageId, proposal.id, "saved"),
      });
    } else {
      confirmWrite.mutate(
        { proposal, force: false },
        {
          onSuccess: () => markProposal(messageId, proposal.id, "saved"),
          onError: (err) => {
            if (err instanceof ApiError && err.status === 409) {
              const detail = err.detail as
                | { existing_record?: { id?: string } }
                | undefined;
              markProposal(
                messageId,
                proposal.id,
                "duplicate",
                detail?.existing_record?.id,
              );
              return;
            }
            updateActive((conv) =>
              appendMessage(conv, {
                id: uuid(),
                role: "assistant",
                content: "",
                error: t("records.createFailed"),
              }),
            );
          },
        },
      );
    }
  };

  const clearCurrentChat = () => {
    if (!current) return;
    deleteConversation(current.id);
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
    <div className="flex h-[calc(100dvh-8rem)] w-full flex-col gap-4 md:h-[calc(100dvh-4rem)] md:flex-row">
      <ConversationList
        store={store}
        activeId={store.activeId}
        onSelect={selectConversation}
        onDelete={deleteConversation}
        onNew={newChat}
        className="hidden md:flex"
      />
      <div className="flex min-w-0 flex-1 flex-col gap-4">
      <PageHeader
        title={t("ai.title")}
        actions={
          <>
            <Button
              variant="outline"
              className="h-9 md:hidden"
              onClick={() => setConversationsOpen(true)}
              title={t("ai.conversations")}
              aria-label={t("ai.conversations")}
            >
              <PanelLeftOpen className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              onClick={newChat}
              title={t("ai.newChat")}
              aria-label={t("ai.newChat")}
              className="h-9 md:hidden"
            >
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">{t("ai.newChat")}</span>
            </Button>
            {current && current.messages.length > 0 ? (
              <Button
                variant="ghost"
                size="icon"
                onClick={clearCurrentChat}
                title={t("ai.deleteChat")}
                aria-label={t("ai.deleteChat")}
                className="h-9 w-9 text-muted-foreground hover:text-danger"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            ) : null}
          </>
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
            className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto py-4"
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
                  {msg.role === "user" && messageImages[msg.id] ? (
                    <ChatImage
                      src={messageImages[msg.id]}
                      className="mb-2 max-h-48 w-auto rounded-lg"
                    />
                  ) : null}

                  {msg.role === "assistant" && msg.reasoning ? (
                    <ReasoningBlock
                      text={msg.reasoning}
                      streaming={streamingId === msg.id && !msg.content}
                      label={t("ai.reasoning")}
                    />
                  ) : null}

                  {msg.role === "assistant" &&
                  streamingId === msg.id &&
                  !msg.content &&
                  !msg.reasoning ? (
                    <div className="flex items-center gap-1 py-1">
                      <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" />
                    </div>
                  ) : msg.error ? (
                    <p className="whitespace-pre-wrap">{msg.error}</p>
                  ) : msg.role === "assistant" ? (
                    // Model replies are Markdown (the journal prompt even asks
                    // for it); render them safely instead of as raw text.
                    <Markdown content={msg.content} />
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
                          onForce={() =>
                            confirmWrite.mutate(
                              { proposal, force: true },
                              {
                                onSuccess: () =>
                                  markProposal(msg.id, proposal.id, "saved"),
                              },
                            )
                          }
                          onCancel={() => markProposal(msg.id, proposal.id, "cancelled")}
                          saving={
                            confirmWrite.isPending || confirmDelete.isPending
                          }
                        />
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          <div className="mx-auto flex w-full max-w-3xl flex-col gap-2 border-t border-border/60 pb-1 pt-3">
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
                disabled={Boolean(streamingId)}
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
                disabled={Boolean(streamingId)}
                rows={1}
                className="min-h-10 flex-1 resize-none rounded-xl border border-border bg-card px-3.5 py-2 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-muted-foreground/80 focus:border-primary/50 focus:ring-2 focus:ring-ring/25 disabled:opacity-50"
              />
              <Button
                type="button"
                size="icon"
                onClick={() => void handleSend()}
                disabled={Boolean(streamingId) || (!input.trim() && !imagePreview)}
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}
      </div>

      <BottomSheet
        open={conversationsOpen}
        onClose={() => setConversationsOpen(false)}
        title={t("ai.conversations")}
      >
        <ConversationList
          store={store}
          activeId={store.activeId}
          onSelect={selectConversation}
          onDelete={deleteConversation}
          onNew={newChat}
          className="flex"
        />
      </BottomSheet>
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

/**
 * Conversation switcher shared by the desktop sidebar and the mobile sheet.
 * Shows the newest activity first; each row is a titled button with a delete
 * affordance, and the active conversation is highlighted.
 */
function ConversationList({
  store,
  activeId,
  onSelect,
  onDelete,
  onNew,
  className,
}: {
  store: ConversationStore;
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
  className?: string;
}) {
  const { t, locale } = useI18n();
  const conversations = sortByUpdated(store.conversations);

  return (
    <aside
      className={cn(
        "flex w-full shrink-0 flex-col gap-3 overflow-y-auto rounded-2xl border border-border bg-card/50 p-3 md:w-64",
        className,
      )}
    >
      <Button
        variant="outline"
        onClick={onNew}
        title={t("ai.newChat")}
        aria-label={t("ai.newChat")}
        className="h-9 w-full shrink-0"
      >
        <Plus className="h-4 w-4" />
        {t("ai.newChat")}
      </Button>

      <span className="px-1 text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground/80">
        {t("ai.conversations")}
      </span>

      {conversations.length === 0 ? (
        <p className="px-2 py-6 text-center text-xs text-muted-foreground">
          {t("ai.noConversations")}
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {conversations.map((conversation) => {
            const active = conversation.id === activeId;
            return (
              <li key={conversation.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelect(conversation.id)}
                  aria-current={active ? "true" : undefined}
                  title={conversation.title || t("ai.untitledChat")}
                  className={cn(
                    "w-full cursor-pointer rounded-lg px-3 py-2 pr-9 text-left transition-colors",
                    active
                      ? "bg-accent text-accent-foreground"
                      : "text-foreground hover:bg-muted",
                  )}
                >
                  <span className="block truncate text-sm font-medium">
                    {conversation.title || t("ai.untitledChat")}
                  </span>
                  <span className="block truncate text-[11px] text-muted-foreground">
                    {formatZonedDateTime(conversation.updatedAt, locale, null)}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(conversation.id)}
                  aria-label={t("ai.deleteChat")}
                  title={t("ai.deleteChat")}
                  className="absolute right-1 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground/50 transition-colors hover:bg-muted hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}

function ProposalCard({
  proposal,
  onSave,
  onForce,
  onCancel,
  saving,
}: {
  proposal: AiProposal & {
    status?: "pending" | "saved" | "cancelled" | "duplicate";
  };
  onSave: () => void;
  onForce: () => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const { t, locale } = useI18n();
  const isDelete = proposal.action.startsWith("delete");
  const isUpdate = proposal.action.startsWith("update");
  const isAddToTrip = proposal.action === "add_place_to_trip";
  const verb = isDelete
    ? t("ai.proposal.delete")
    : isUpdate
      ? t("ai.proposal.update")
      : isAddToTrip
        ? t("ai.proposal.addToTrip")
        : t("ai.proposal.create");
  const saved = proposal.status === "saved";
  const cancelled = proposal.status === "cancelled";
  const duplicate = proposal.status === "duplicate";
  const dataLines = isDelete ? [] : formatProposalData(proposal, t, locale);

  if (duplicate) {
    const base =
      proposal.record_type === "flight"
        ? "flights"
        : proposal.record_type === "train"
          ? "trains"
          : proposal.record_type === "hotel"
            ? "hotels"
            : proposal.record_type === "trip"
              ? "trips"
              : proposal.record_type === "expense"
                ? "expenses"
                : proposal.record_type === "note"
                  ? "notes"
                  : proposal.record_type === "place"
                    ? "places"
                    : proposal.record_type === "activity"
                      ? "activities"
                      : "transports";
    return (
      <div className="rounded-lg border border-warning/40 bg-warning/5 px-3 py-2.5">
        <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-warning">
          <AlertTriangle className="h-3.5 w-3.5" />
          <span>{t("records.duplicateTitle")}</span>
        </div>
        <p className="mb-2 text-xs text-muted-foreground">
          {t("records.duplicateDescription")}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {proposal.existingRecordId ? (
            <Link href={`/${base}/${proposal.existingRecordId}`}>
              <Button size="sm" variant="outline">
                {t("records.duplicateOpenExisting")}
              </Button>
            </Link>
          ) : null}
          <Button size="sm" onClick={onForce} disabled={saving}>
            {t("records.duplicateKeepNew")}
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>
            {t("ai.cancel")}
          </Button>
        </div>
      </div>
    );
  }

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
          {verb} {proposal.record_type}
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
