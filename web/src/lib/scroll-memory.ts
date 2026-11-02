/** Remember a list page's scroll position so returning from a detail page
 *  lands where the user left off. Session-scoped: survives the hard
 *  navigation after delete (window.location.assign), dies with the tab. */

const PREFIX = "azmark:scroll:";

export function saveScroll(path: string) {
  try {
    sessionStorage.setItem(PREFIX + path, String(window.scrollY));
  } catch {
    /* private mode etc. — degrade to the old top-of-page behavior */
  }
}

export function takeScroll(path: string): number | null {
  try {
    const raw = sessionStorage.getItem(PREFIX + path);
    if (raw === null) return null;
    sessionStorage.removeItem(PREFIX + path);
    const y = Number(raw);
    return Number.isFinite(y) && y > 0 ? y : null;
  } catch {
    return null;
  }
}
