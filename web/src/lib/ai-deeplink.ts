/**
 * One-shot deep-link prompts for the AI page (`/ai?q=...`).
 *
 * The trip page's「AI 写回忆」button links here with the journal request as
 * `q`. The AI page consumes the parameter at most once: it removes `q` from
 * the URL before auto-sending, so a refresh (or React StrictMode's doubled
 * mount effect) cannot replay the same request. Kept pure so the consume
 * semantics are pinned by the Node test runner, following the ai-history /
 * ai-conversations pattern.
 */

export interface DeepLinkPrompt {
  /** Decoded prompt from `?q=`; empty string when the parameter was blank. */
  prompt: string;
  /** `href` with the one-shot `q` parameter removed. */
  href: string;
}

/**
 * Return the deep-link prompt and the cleaned href, or `null` when the URL
 * carries no `q` parameter. The caller navigates to `href` with
 * `history.replaceState` after this returns, making the prompt one-shot.
 */
export function consumeDeepLinkPrompt(href: string): DeepLinkPrompt | null {
  const url = new URL(href);
  if (!url.searchParams.has("q")) return null;
  const prompt = url.searchParams.get("q") ?? "";
  url.searchParams.delete("q");
  return { prompt, href: url.toString() };
}