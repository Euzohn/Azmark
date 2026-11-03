import assert from "node:assert/strict";
import test from "node:test";
import { buildChatHistory, MAX_HISTORY_CONTENT } from "./ai-history.ts";

test("history keeps roles, text and proposal outcomes in order", () => {
  const history = buildChatHistory([
    { role: "user", content: "  记录一下 CX659  " },
    {
      role: "assistant",
      content: "我准备创建这条航班。",
      proposals: [
        { action: "create", record_type: "flight", summary: "Create Flight · CX659", status: "saved" },
        { action: "create", record_type: "hotel", summary: "Create Hotel · Marina Bay", status: "cancelled" },
      ],
    },
    { role: "user", content: "好的" },
  ]);
  assert.equal(history.length, 3);
  assert.deepEqual(history[0], { role: "user", content: "记录一下 CX659" });
  assert.equal(history[1].role, "assistant");
  assert.equal(history[1].content, "我准备创建这条航班。");
  assert.deepEqual(history[1].proposals, [
    { action: "create", record_type: "flight", summary: "Create Flight · CX659", status: "saved" },
    { action: "create", record_type: "hotel", summary: "Create Hotel · Marina Bay", status: "cancelled" },
  ]);
  assert.deepEqual(history[2], { role: "user", content: "好的" });
});

test("history defaults unresolved proposals to pending", () => {
  const [turn] = buildChatHistory([
    {
      role: "assistant",
      content: "",
      proposals: [{ action: "update", record_type: "trip", summary: "Update Trip" }],
    },
  ]);
  assert.deepEqual(turn, {
    role: "assistant",
    content: "",
    proposals: [{ action: "update", record_type: "trip", summary: "Update Trip", status: "pending" }],
  });
});

test("history skips streaming placeholders, error bubbles and empty turns", () => {
  const history = buildChatHistory([
    { role: "user", content: "hi" },
    { role: "assistant", content: "partial", streaming: true },
    { role: "assistant", content: "", error: "boom" },
    { role: "assistant", content: "   " },
    { role: "user", content: "again" },
  ]);
  assert.deepEqual(
    history.map((turn) => turn.content),
    ["hi", "again"],
  );
});

test("history truncates long text and keeps only the most recent turns", () => {
  const long = "x".repeat(MAX_HISTORY_CONTENT + 500);
  const history = buildChatHistory(
    [
      { role: "user", content: long },
      ...Array.from({ length: 5 }, (_, index) => ({
        role: "user" as const,
        content: `turn ${index}`,
      })),
    ],
    3,
  );
  assert.equal(history.length, 3);
  assert.deepEqual(
    history.map((turn) => turn.content),
    ["turn 2", "turn 3", "turn 4"],
  );
  assert.equal(buildChatHistory([{ role: "user", content: long }])[0].content.length, MAX_HISTORY_CONTENT);
});
