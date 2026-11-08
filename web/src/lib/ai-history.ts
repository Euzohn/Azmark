import type { AiHistoryMessage } from "@/lib/types";

/**
 * The backend is stateless: every request carries only the current message.
 * Prior turns — including what the user did with earlier proposals (saved /
 * cancelled / duplicate) — are relayed from the local chat history so the
 * assistant can follow up without re-proposing work the user already accepted.
 */

export interface ChatHistorySource {
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
  error?: string;
  streaming?: boolean;
  proposals?: Array<{
    action: string;
    record_type: string;
    summary: string;
    status?: "pending" | "saved" | "cancelled" | "duplicate";
  }>;
}

/** Most recent turns sent back; older context is dropped, not summarized. */
export const MAX_HISTORY_TURNS = 12;
/** Per-message cap. The backend accepts up to 4000; keep headroom for safety. */
export const MAX_HISTORY_CONTENT = 2000;
/** Keep reasoning in history for continuity, but never resend a novel. */
export const MAX_HISTORY_REASONING = 8000;

export function buildChatHistory(
  messages: ChatHistorySource[],
  limit: number = MAX_HISTORY_TURNS,
): AiHistoryMessage[] {
  const turns: AiHistoryMessage[] = [];
  for (const message of messages) {
    // Skip the in-flight placeholder and local error bubbles — neither is part
    // of the conversation the assistant should reason about.
    if (message.streaming || message.error) continue;

    const content = message.content.trim().slice(0, MAX_HISTORY_CONTENT);
    const proposals =
      message.role === "assistant" && message.proposals?.length
        ? message.proposals.map((proposal) => ({
            action: proposal.action,
            record_type: proposal.record_type,
            summary: proposal.summary,
            status: proposal.status ?? ("pending" as const),
          }))
        : undefined;

    // A proposal-only assistant turn has no text but is still meaningful.
    if (!content && !proposals) continue;

    const reasoning =
      message.role === "assistant" && message.reasoning
        ? message.reasoning.slice(0, MAX_HISTORY_REASONING)
        : undefined;

    const turn: AiHistoryMessage = proposals
      ? { role: message.role, content, proposals }
      : { role: message.role, content };
    if (reasoning) turn.reasoning = reasoning;
    turns.push(turn);
  }
  return turns.slice(-Math.max(0, limit));
}
