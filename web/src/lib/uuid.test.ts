/**
 * Run with `npm test` (Node's built-in test runner; no extra dependencies).
 *
 * uuid() must work on plain-HTTP deployments where crypto.randomUUID is
 * undefined (secure-context-only API). These tests pin the RFC 4122 v4
 * formatting of the fallback and the shape of uuid() itself.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import { uuid, uuidV4FromBytes } from "./uuid.ts";

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

test("uuid() returns well-formed v4 UUIDs", () => {
  for (let i = 0; i < 100; i++) {
    const value = uuid();
    assert.match(value, UUID_V4);
  }
});

test("uuidV4FromBytes stamps version and variant on the given bytes", () => {
  // Deterministic input → deterministic output, and the caller's buffer
  // must not be mutated.
  const bytes = new Uint8Array(16).fill(0xff);
  const value = uuidV4FromBytes(bytes);
  assert.equal(value, "ffffffff-ffff-4fff-bfff-ffffffffffff");
  assert.equal(bytes[6], 0xff);
  assert.equal(bytes[8], 0xff);
});

test("uuidV4FromBytes rejects buffers that are not 16 bytes", () => {
  assert.throws(() => uuidV4FromBytes(new Uint8Array(8)), /16 bytes/);
});
