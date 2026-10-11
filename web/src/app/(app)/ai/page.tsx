"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Send, Sparkles, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRef, useState, useEffect } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { AiProposal } from "@/lib/types";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  proposals?: AiProposal[];
  pending?: boolean;
  error?: boolean;
}

let _msgId = 0;
function nextId(): string {
  _msgId += 1;
  return `msg-${_msgId}`;
}

export default function AiChatPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: aiSettings } = useQuery({
    queryKey: ["ai-settings"],
    queryFn: api.getAiSettings,
  });

  const configured = aiSettings?.configured ?? false;

  const send = useMutation({
    mutationFn: (message: string) => api.chatAi(message),
    onSuccess: (response) => {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: response.reply,
          proposals: response.proposals,
        },
      ]);
    },
    onError: (err: unknown) => {
      const detail =
        err instanceof ApiError ? err.message : t("ai.error");
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: detail,
          error: true,
        },
      ]);
    },
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSend = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = input.trim();
    if (!text || send.isPending) return;
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content: text },
    ]);
    setInput("");
    send.mutate(text);
  };

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
      const id = (proposal.data as Record<string, unknown>).record_id as string;
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
                p.id === proposalId ? { ...p, status: status as never } : p,
              ),
            }
          : msg,
      ),
    );
  };

  return (
    <div className="flex h-[calc(100dvh-8rem)] flex-col gap-4 md:h-[calc(100dvh-4rem)]">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-[#c26b30] text-primary-foreground shadow-md shadow-primary/25">
          <Bot className="h-5 w-5" strokeWidth={1.75} />
        </div>
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">
            {t("ai.title")}
          </h1>
        </div>
      </div>

      {!configured ? (
        <EmptyState
          icon={Sparkles}
          title={t("ai.notConfigured")}
          hint={t("ai.notConfiguredHint")}
          action={
            <Link href="/settings">
              <Button variant="outline">
                {t("ai.goToSettings")}
              </Button>
            </Link>
          }
        />
      ) : (
        <>
          <div
            ref={scrollRef}
            className="flex flex-1 flex-col gap-4 overflow-y-auto rounded-2xl border border-border bg-card/50 p-4"
          >
            {messages.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
                <Bot className="h-10 w-10 text-muted-foreground" strokeWidth={1.5} />
                <p className="font-display text-lg font-medium">{t("ai.empty")}</p>
                <p className="max-w-md text-sm text-muted-foreground">
                  {t("ai.emptyHint")}
                </p>
              </div>
            ) : null}

            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : msg.error
                        ? "bg-danger/10 text-danger"
                        : "bg-accent text-accent-foreground"
                  }`}
                >
                  {msg.role === "assistant" && msg.pending ? (
                    <span className="text-muted-foreground">{t("ai.thinking")}</span>
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

          <form onSubmit={handleSend} className="flex items-center gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t("ai.placeholder")}
              disabled={send.isPending}
              className="flex-1"
            />
            <Button type="submit" size="icon" disabled={send.isPending || !input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </form>
        </>
      )}
    </div>
  );
}

function ProposalCard({
  proposal,
  onSave,
  onCancel,
  saving,
}: {
  proposal: AiProposal & { status?: string };
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const { t } = useI18n();
  const isDelete = proposal.action === "delete_transport";
  const saved = proposal.status === "saved";
  const cancelled = proposal.status === "cancelled";

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
      <p className="mb-2 text-sm text-muted-foreground">{proposal.summary}</p>
      <div className="flex items-center gap-2">
        <Button size="sm" variant={isDelete ? "danger" : "default"} onClick={onSave} disabled={saving}>
          {t("ai.save")}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>
          {t("ai.cancel")}
        </Button>
      </div>
    </div>
  );
}
