/**
 * Azmark "folded AZ" monogram. The symbol body uses `currentColor` so it
 * adapts to the tile it sits in; the destination dot uses `var(--primary)`
 * (saffron) which also flips with the theme, giving correct contrast whether
 * the tile is ink-on-paper or paper-on-ink.
 *
 * Shape sourced from the azmark-svg brand set, palette is "Ink & Saffron".
 */
export function AzmarkMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 208 120"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <g fill="currentColor">
        <path d="M8.5 97 C8.5 99.5 9.5 100 11.5 100 H30 Q33 100 34.2 96 L73 36 Q75.5 32.8 78 36 L101 72 Q103 74 105 71 C108.5 66.5 110 63 110 61 C110 55 105 46 101 33 C97 20 89 9 80 8 C73 8 66 12 61 20 Z" />
        <rect x="112" y="33" width="57" height="15" rx="7.5" />
        <rect x="102" y="92" width="72.5" height="19" rx="9.5" />
      </g>
      <path
        d="M158 44 L110 100"
        fill="none"
        stroke="currentColor"
        strokeWidth={23}
        strokeLinecap="round"
      />
      <circle cx="191.5" cy="85.5" r="11" fill="var(--primary)" />
    </svg>
  );
}
