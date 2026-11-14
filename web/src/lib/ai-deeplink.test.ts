import assert from "node:assert/strict";
import test from "node:test";
import { consumeDeepLinkPrompt } from "./ai-deeplink.ts";

test("deep link extracts and decodes the journal prompt", () => {
  const consumed = consumeDeepLinkPrompt(
    "https://azmark.example/ai?q=%E5%B8%AE%E6%88%91%E5%86%99%E4%B8%80%E4%BB%BD%E3%80%8CSG%202026%E3%80%8D%E7%9A%84%E6%97%85%E8%A1%8C%E5%9B%9E%E5%BF%86",
  );
  assert.ok(consumed);
  assert.equal(consumed.prompt, "帮我写一份「SG 2026」的旅行回忆");
  assert.equal(consumed.href, "https://azmark.example/ai");
});

test("deep link keeps unrelated query parameters", () => {
  const consumed = consumeDeepLinkPrompt("https://azmark.example/ai?lang=en-US&q=hello");
  assert.ok(consumed);
  assert.equal(consumed.prompt, "hello");
  assert.equal(consumed.href, "https://azmark.example/ai?lang=en-US");
});

test("no q parameter means nothing to consume", () => {
  assert.equal(consumeDeepLinkPrompt("https://azmark.example/ai"), null);
});

test("blank q is consumed without a prompt", () => {
  const consumed = consumeDeepLinkPrompt("https://azmark.example/ai?q=");
  assert.ok(consumed);
  assert.equal(consumed.prompt, "");
  assert.equal(consumed.href, "https://azmark.example/ai");
});