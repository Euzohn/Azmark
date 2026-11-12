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
 * The store key is scoped per user id (`azmark-ai-conversations:v1:<userId>`):
 * chat history is private to the account that wrote it. Before this isolation
 * the history lived under two shared keys — the single-history
 * `azmark-ai-chat-history` and the pre-isolation multi-conversation key — so
 * signing in with a different account on the same browser revealed the
 * previous account's chats. On first load, a non-admin account adopts the
 * shared leftovers and the shared keys are removed; admins read (and write)
 * only their own key.
 */

import type { AiProposal } from "./types";

/** Shared keys from before per-user isolation (one history for every account). */
export const LEGACY_HISTORY_KEY = "azmark-ai-chat-history";
export const LEGACY_SHARED_KEY = "azmark-ai-conversations";

/** Per-user key: chat history is private to the account that wrote it. */
export function conversationsKey(userId: string): string {
  return `azmark-ai-conversations:v1:${userId}`;
}

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
  reasoning?: string;
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
    // Prune empty conversations: a "new chat" that was never sent into is
    // worthless, and keeping it would litter the list forever.
    const conversations = data.conversations.filter(
      (c): c is Conversation =>
        Boolean(c && typeof c.id === "string" && Array.isArray(c.messages) && c.messages.length > 0),
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

/**
 * Combine pre-isolation leftovers into one store for adoption, preferring the
 * newer multi-conversation data. Pure so it can be pinned by unit tests.
 */
export function mergeLegacyStores(
  legacy: ConversationStore,
  shared: ConversationStore | null,
): ConversationStore | null {
  const usable = shared && shared.conversations.length > 0 ? shared : null;
  if (usable && legacy.conversations.length > 0) {
    return {
      ...usable,
      conversations: [...legacy.conversations, ...usable.conversations],
    };
  }
  if (usable) return usable;
  return legacy.conversations.length > 0 ? legacy : null;
}

/**
 * Load the signed-in account's store. When the per-user key is absent, the
 * pre-isolation leftovers — the single-history key and the shared
 * multi-conversation key every account used to read — are adopted by the
 * first *non-admin* signed-in account opening the AI page, then the shared
 * keys are removed. Admins never adopt: the shared leftovers are regular
 * users' chat history, and this keeps the isolation guarantee even if an
 * admin logs in before the original author after the upgrade.
 */
export function loadStore(userId: string, adoptShared = true): ConversationStore {
  if (typeof window === "undefined") return emptyStore();
  const stored = parseStore(window.localStorage.getItem(conversationsKey(userId)));
  if (stored) return stored;

  const adopted = adoptShared
    ? mergeLegacyStores(
        migrateLegacy(parseLegacy(window.localStorage.getItem(LEGACY_HISTORY_KEY))),
        parseStore(window.localStorage.getItem(LEGACY_SHARED_KEY)),
      )
    : null;
  if (adopted) {
    saveStore(adopted, userId);
    window.localStorage.removeItem(LEGACY_HISTORY_KEY);
    window.localStorage.removeItem(LEGACY_SHARED_KEY);
  }
  return adopted ?? emptyStore();
}

export function saveStore(store: ConversationStore, userId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(conversationsKey(userId), JSON.stringify(store));
  } catch {
    // localStorage quota exceeded — drop the write rather than crash the page.
  }
}
