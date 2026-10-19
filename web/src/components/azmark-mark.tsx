export function AzmarkMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 120 100"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth={10}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 78 L43 20 Q47 12 52 21 L66 43" />
        <path d="M69 40 H96 L66 72 H94" />
      </g>
      <circle cx="106" cy="72" r="6.5" fill="#C66B4E" />
    </svg>
  );
}
