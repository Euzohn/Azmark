/**
 * Client-side multi-conversation store for the AI page.
 *
 * The backend is stateless (spec #29–#34): it never stores chat turns, so all
 * conversations live in localStorage. This module keeps the pure data-shape
 * helpers separate from persistence so they can be unit-tested under Node.
 *
 * Storage shape (versioned for future migrations):
 *   { version: 1, activeId, conversations: Conversation[] }
 *
 * Before multi-conversation support there was a single array under
 * `azmark-ai-chat-history`; that is migrated into one conversation on first
 * load so nobody loses their existing chat.
 */

import type { AiProposal } from "./types";

export const CONVERSATIONS_KEY = "azmark-ai-conversations";
export const LEGACY_HISTORY_KEY = "azmark-ai-chat-history";

let _seq = 0;

/**
 * Locally unique id for a conversation/message. Kept dependency-free so this
 * module stays importable by the Node test runner (which cannot resolve the
 * bundler's `@/` alias) as well as by the Next build.
 */
function newId(): string {
  _seq += 1;
  return `${Date.now().toString(36)}-${_seq}-${Math.random().toString(36).slice(2, 10)}`;
}

/** A persisted turn. Transient UI fields (image, streaming) are not stored. */
export interface StoredMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  proposals?: AiProposal[];
  error?: string;
}

export interface Conversation {
  id: string;
  /** Derived from the first user message; empty means "untitled". */
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: StoredMessage[];
}

export interface ConversationStore {
  version: 1;
  activeId: string | null;
  conversations: Conversation[];
}

export function emptyStore(): ConversationStore {
  return { version: 1, activeId: null, conversations: [] };
}

export function createConversation(now: Date = new Date()): Conversation {
  const iso = now.toISOString();
  return { id: newId(), title: "", createdAt: iso, updatedAt: iso, messages: [] };
}

/** First line of the first user message, trimmed and capped for the list. */
export function deriveTitle(content: string, max = 40): string {
  const firstLine = content.trim().split("\n")[0].trim();
  if (!firstLine) return "";
  return firstLine.length > max ? `${firstLine.slice(0, max - 1)}…` : firstLine;
}

/** Newest activity first — the list shows recent conversations on top. */
export function sortByUpdated(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function findConversation(
  store: ConversationStore,
  id: string | null,
): Conversation | undefined {
  return id ? store.conversations.find((c) => c.id === id) : undefined;
}

export function activeConversation(store: ConversationStore): Conversation | undefined {
  return findConversation(store, store.activeId);
}

/** Append a message, promoting the first user message to the conversation title. */
export function appendMessage(
  conversation: Conversation,
  message: StoredMessage,
  now: Date = new Date(),
): Conversation {
  const title =
    conversation.title || (message.role === "user" ? deriveTitle(message.content) : "");
  return {
    ...conversation,
    title,
    messages: [...conversation.messages, message],
    updatedAt: now.toISOString(),
  };
}

export function patchMessage(
  conversation: Conversation,
  messageId: string,
  patch: Partial<StoredMessage>,
  now: Date = new Date(),
): Conversation {
  return {
    ...conversation,
    messages: conversation.messages.map((m) =>
      m.id === messageId ? { ...m, ...patch } : m,
    ),
    updatedAt: now.toISOString(),
  };
}

/** Insert or replace a conversation, returning a new store (active unchanged). */
export function upsertConversation(
  store: ConversationStore,
  conversation: Conversation,
): ConversationStore {
  const exists = store.conversations.some((c) => c.id === conversation.id);
  return {
    ...store,
    conversations: exists
      ? store.conversations.map((c) => (c.id === conversation.id ? conversation : c))
      : [conversation, ...store.conversations],
  };
}

export function removeConversation(
  store: ConversationStore,
  id: string,
): ConversationStore {
  const conversations = store.conversations.filter((c) => c.id !== id);
  const activeId =
    store.activeId === id ? (sortByUpdated(conversations)[0]?.id ?? null) : store.activeId;
  return { ...store, conversations, activeId };
}

/**
 * Wrap legacy single-history messages into one conversation. Returns an empty
 * store when the legacy key held nothing usable.
 */
export function migrateLegacy(
  messages: StoredMessage[],
  now: Date = new Date(),
): ConversationStore {
  const cleaned = messages.filter((m) => m.role === "user" || m.role === "assistant");
  if (cleaned.length === 0) return emptyStore();
  const iso = now.toISOString();
  const firstUser = cleaned.find((m) => m.role === "user");
  const conversation: Conversation = {
    id: newId(),
    title: firstUser ? deriveTitle(firstUser.content) : "",
    createdAt: iso,
    updatedAt: iso,
    messages: cleaned,
  };
  return { version: 1, activeId: conversation.id, conversations: [conversation] };
}

// ---------------------------------------------------------------------------
//  Persistence (browser only; callers must be client components)
// ---------------------------------------------------------------------------

function parseStore(raw: string | null): ConversationStore | null {
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as Partial<ConversationStore>;
    if (data.version !== 1 || !Array.isArray(data.conversations)) return null;
    const conversations = data.conversations.filter(
      (c): c is Conversation => Boolean(c && typeof c.id === "string"),
    );
    const activeId =
      data.activeId && conversations.some((c) => c.id === data.activeId)
        ? data.activeId
        : (sortByUpdated(conversations)[0]?.id ?? null);
    return { version: 1, activeId, conversations };
  } catch {
    return null;
  }
}

function parseLegacy(raw: string | null): StoredMessage[] {
  if (!raw) return [];
  try {
    const data = JSON.parse(raw) as Array<Partial<StoredMessage>>;
    if (!Array.isArray(data)) return [];
    return data
      .filter((m) => m && (m.role === "user" || m.role === "assistant"))
      .map((m) => ({
        id: typeof m.id === "string" ? m.id : newId(),
        role: m.role as "user" | "assistant",
        content: typeof m.content === "string" ? m.content : "",
        proposals: m.proposals,
        error: m.error,
      }));
  } catch {
    return [];
  }
}

/** Load the store, migrating the legacy single-history key if needed. */
export function loadStore(): ConversationStore {
  if (typeof window === "undefined") return emptyStore();
  const stored = parseStore(window.localStorage.getItem(CONVERSATIONS_KEY));
  if (stored) return stored;

  const legacy = migrateLegacy(parseLegacy(window.localStorage.getItem(LEGACY_HISTORY_KEY)));
  if (legacy.conversations.length > 0) {
    saveStore(legacy);
    window.localStorage.removeItem(LEGACY_HISTORY_KEY);
  }
  return legacy;
}

export function saveStore(store: ConversationStore): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(store));
  } catch {
    // localStorage quota exceeded — drop the write rather than crash the page.
  }
}
