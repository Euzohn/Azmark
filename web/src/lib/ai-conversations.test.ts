/**
 * Run with `npm test` (Node's built-in test runner; no extra dependencies).
 *
 * Multi-conversation support is pure client-side state, so these tests pin the
 * data-shape helpers: title derivation, message append/patch, conversation
 * upsert/remove/active-selection, and migration of the legacy single history.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  appendMessage,
  conversationsKey,
  createConversation,
  deriveTitle,
  emptyStore,
  mergeLegacyStores,
  migrateLegacy,
  patchMessage,
  removeConversation,
  sortByUpdated,
  upsertConversation,
  type ConversationStore,
  type StoredMessage,
} from "./ai-conversations.ts";

const NOW = new Date("2026-01-02T03:04:05.000Z");
const LATER = new Date("2026-01-02T04:00:00.000Z");

function msg(id: string, role: "user" | "assistant", content: string): StoredMessage {
  return { id, role, content };
}

test("deriveTitle uses the first line, trimmed and capped", () => {
  assert.equal(deriveTitle("  记录一下 CX659  "), "记录一下 CX659");
  assert.equal(deriveTitle("第一行\n第二行"), "第一行");
  assert.equal(deriveTitle("   "), "");
  const long = deriveTitle("a".repeat(60));
  assert.equal(long.length, 40);
  assert.ok(long.endsWith("…"));
});

test("appendMessage promotes the first user message to the title", () => {
  const conv = createConversation(NOW);
  const withUser = appendMessage(conv, msg("m1", "user", "帮我查航班 CX659"), LATER);
  assert.equal(withUser.title, "帮我查航班 CX659");
  assert.equal(withUser.messages.length, 1);
  assert.equal(withUser.updatedAt, LATER.toISOString());

  // A later message must not overwrite the derived title.
  const withAssistant = appendMessage(withUser, msg("m2", "assistant", "好的"), LATER);
  assert.equal(withAssistant.title, "帮我查航班 CX659");
  assert.equal(withAssistant.messages.length, 2);
});

test("an assistant-only first turn leaves the conversation untitled", () => {
  const conv = appendMessage(createConversation(NOW), msg("m1", "assistant", "你好"), LATER);
  assert.equal(conv.title, "");
});

test("patchMessage updates one message without touching the rest", () => {
  const conv = appendMessage(
    appendMessage(createConversation(NOW), msg("m1", "user", "hi"), NOW),
    msg("m2", "assistant", ""),
    NOW,
  );
  const patched = patchMessage(conv, "m2", { content: "hello", error: "boom" }, LATER);
  assert.equal(patched.messages[1].content, "hello");
  assert.equal(patched.messages[1].error, "boom");
  assert.equal(patched.messages[0].content, "hi");
  assert.equal(patched.updatedAt, LATER.toISOString());
});

test("upsertConversation inserts new conversations and replaces existing ones", () => {
  const a = createConversation(NOW);
  const b = createConversation(LATER);
  let store = upsertConversation(emptyStore(), a);
  store = upsertConversation(store, b);
  assert.deepEqual(
    store.conversations.map((c) => c.id),
    [b.id, a.id],
  );

  const renamed = { ...a, title: "renamed" };
  store = upsertConversation(store, renamed);
  assert.equal(store.conversations.length, 2);
  assert.equal(store.conversations.find((c) => c.id === a.id)?.title, "renamed");
});

test("removeConversation clears activeId or falls back to the next recent one", () => {
  const a = { ...createConversation(NOW), updatedAt: NOW.toISOString() };
  const b = { ...createConversation(LATER), updatedAt: LATER.toISOString() };
  let store: ConversationStore = { version: 1, activeId: b.id, conversations: [a, b] };

  store = removeConversation(store, b.id);
  assert.equal(store.conversations.length, 1);
  assert.equal(store.activeId, a.id);

  store = removeConversation(store, a.id);
  assert.equal(store.conversations.length, 0);
  assert.equal(store.activeId, null);
});

test("removeConversation keeps activeId when deleting a different conversation", () => {
  const a = createConversation(NOW);
  const b = createConversation(LATER);
  const store: ConversationStore = { version: 1, activeId: a.id, conversations: [a, b] };
  assert.equal(removeConversation(store, b.id).activeId, a.id);
});

test("sortByUpdated orders newest first", () => {
  const old = { ...createConversation(NOW), updatedAt: "2026-01-01T00:00:00.000Z" };
  const recent = { ...createConversation(LATER), updatedAt: "2026-02-01T00:00:00.000Z" };
  assert.deepEqual(
    sortByUpdated([old, recent]).map((c) => c.id),
    [recent.id, old.id],
  );
});

test("migrateLegacy wraps old history into one conversation", () => {
  const store = migrateLegacy(
    [msg("m1", "user", "旧问题"), msg("m2", "assistant", "旧回答")],
    NOW,
  );
  assert.equal(store.conversations.length, 1);
  assert.equal(store.activeId, store.conversations[0].id);
  assert.equal(store.conversations[0].title, "旧问题");
  assert.equal(store.conversations[0].messages.length, 2);
});

test("migrateLegacy of an empty history yields an empty store", () => {
  assert.deepEqual(migrateLegacy([]), emptyStore());
});

test("conversationsKey is scoped per user id", () => {
  assert.equal(conversationsKey("u-1"), "azmark-ai-conversations:v1:u-1");
  assert.notEqual(conversationsKey("u-1"), conversationsKey("u-2"));
});

test("mergeLegacyStores prefers the shared multi-key and combines leftovers", () => {
  const legacy = migrateLegacy(
    [msg("m1", "user", "旧问题"), msg("m2", "assistant", "旧回答")],
    NOW,
  );
  const shared: ConversationStore = {
    version: 1,
    activeId: "c-shared",
    conversations: [
      { id: "c-shared", title: "共享会话", createdAt: LATER.toISOString(), updatedAt: LATER.toISOString(), messages: [msg("m3", "user", "另一个问题")] },
    ],
  };

  const combined = mergeLegacyStores(legacy, shared);
  assert.ok(combined);
  assert.deepEqual(
    combined?.conversations.map((c) => c.id),
    [legacy.conversations[0].id, "c-shared"],
  );
  assert.equal(combined?.activeId, "c-shared");
});

test("mergeLegacyStores falls back to whichever side has data", () => {
  const shared: ConversationStore = {
    version: 1,
    activeId: "c-shared",
    conversations: [],
  };
  assert.equal(mergeLegacyStores(emptyStore(), shared), null);
  assert.equal(mergeLegacyStores(emptyStore(), null), null);

  const legacy = migrateLegacy([msg("m1", "user", "旧问题")], NOW);
  const merged = mergeLegacyStores(legacy, null);
  assert.equal(merged?.conversations.length, 1);
});
