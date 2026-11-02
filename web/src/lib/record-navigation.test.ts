import assert from "node:assert/strict";
import test from "node:test";
import { hotelsReturnHref, parseRecordPage, parseRecordSort, recordsReturnHref } from "./record-navigation.ts";

test("record pagination and sorting reject invalid URL values", () => {
  for (const value of [null, "0", "-1", "1.5", "Infinity", "not-a-page"]) assert.equal(parseRecordPage(value), 1);
  assert.equal(parseRecordPage("4"), 4);
  assert.equal(parseRecordSort("arrival"), "arrival");
  assert.equal(parseRecordSort("invalid"), "newest");
});

test("record return links preserve filters but reject redirects", () => {
  assert.equal(recordsReturnHref("/records?type=flight&page=3&search=HKG"), "/records?type=flight&page=3&search=HKG");
  for (const value of [null, "https://evil.example/records", "//evil.example/records", "/account", "javascript:alert(1)"]) assert.equal(recordsReturnHref(value), "/records?type=flight");
});

test("hotel return links preserve search but reject redirects", () => {
  assert.equal(hotelsReturnHref("/hotels?search=%E4%B8%9C%E4%BA%AC"), "/hotels?search=%E4%B8%9C%E4%BA%AC");
  for (const value of [null, "https://evil.example/hotels", "//evil.example/hotels", "/records", "javascript:alert(1)"]) assert.equal(hotelsReturnHref(value), "/hotels");
});
