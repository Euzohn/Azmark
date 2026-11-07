/**
 * crypto.randomUUID() is only exposed in secure contexts (HTTPS or
 * localhost), so plain-HTTP deployments would throw "crypto.randomUUID
 * is not a function" — the request dies before it is ever sent. The
 * fallback below is built on getRandomValues, which works everywhere.
 */

function toHex(bytes: Uint8Array): string {
  let out = "";
  for (const byte of bytes) out += byte.toString(16).padStart(2, "0");
  return out;
}

/** Format 16 raw bytes as an RFC 4122 version-4 UUID (exposed for tests). */
export function uuidV4FromBytes(bytes: Uint8Array): string {
  if (bytes.length !== 16) throw new Error("a v4 UUID needs exactly 16 bytes");
  const copy = bytes.slice();
  copy[6] = (copy[6] & 0x0f) | 0x40; // version 4
  copy[8] = (copy[8] & 0x3f) | 0x80; // RFC variant
  const hex = toHex(copy);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function uuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return uuidV4FromBytes(crypto.getRandomValues(new Uint8Array(16)));
}
