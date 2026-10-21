import { cn } from "@/lib/utils";

/**
 * Branded loading animation: a saffron marker travels along the Z path and
 * arrives at the destination dot. The symbol body uses `currentColor` and the
 * marker / destination use `var(--primary)` (saffron), so the loader adapts to
 * the active theme (ink-on-paper or paper-on-ink).
 *
 * Source shape: assets/loading/azmark-loader.svg. Respects
 * prefers-reduced-motion (the travelling marker is hidden; the static
 * monogram + destination dot remain).
 */
export function AzmarkLoader({
  className,
  label,
}: {
  className?: string;
  label?: string;
}) {
  return (
    <svg
      viewBox="0 0 224 136"
      role={label ? "status" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      className={cn("overflow-visible", className)}
    >
      <style>{`.az-route{opacity:0}.az-traveler{opacity:0}@media (prefers-reduced-motion: reduce){.az-route,.az-traveler,.az-pulse{display:none}}`}</style>
      <g transform="translate(8 8)">
        <g fill="currentColor">
          <path d="M8.5 97 C8.5 99.5 9.5 100 11.5 100 H30 Q33 100 34.2 96 L73 36 Q75.5 32.8 78 36 L101 72 Q103 74 105 71 C108.5 66.5 110 63 110 61 C110 55 105 46 101 33 C97 20 89 9 80 8 C73 8 66 12 61 20 Z" />
          <rect x="112" y="33" width="57" height="15" rx="7.5" />
          <rect x="102" y="92" width="72.5" height="19" rx="9.5" />
          <path
            d="M158 44 L110 100"
            fill="none"
            stroke="currentColor"
            strokeWidth={23}
            strokeLinecap="round"
          />
        </g>

        <path
          className="az-route"
          d="M117.5 40.5 L156 40.5 C161.8 40.5 163.6 42.4 160.8 46.2 L113.8 97.2 C111 100.6 111.8 101.5 116.2 101.5 L165.8 101.5 C170.8 101.5 173.4 99.1 176.2 95.4 L191.5 85.5"
          pathLength={100}
          fill="none"
          stroke="var(--primary)"
          strokeWidth={1.7}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeDasharray="100"
          strokeDashoffset="100"
        >
          <animate
            attributeName="stroke-dashoffset"
            values="100;0;0"
            keyTimes="0;.82;1"
            dur="3.8s"
            repeatCount="indefinite"
          />
          <animate
            attributeName="opacity"
            values="0;.52;.52;0"
            keyTimes="0;.04;.9;1"
            dur="3.8s"
            repeatCount="indefinite"
          />
        </path>

        <g className="az-traveler" aria-hidden="true">
          <circle r="10.5" fill="var(--primary)" opacity=".12" />
          <circle r="3.7" fill="var(--primary)" />
          <animateMotion
            path="M117.5 40.5 L156 40.5 C161.8 40.5 163.6 42.4 160.8 46.2 L113.8 97.2 C111 100.6 111.8 101.5 116.2 101.5 L165.8 101.5 C170.8 101.5 173.4 99.1 176.2 95.4 L191.5 85.5"
            keyPoints="0;1;1"
            keyTimes="0;.82;1"
            calcMode="linear"
            dur="3.8s"
            repeatCount="indefinite"
          />
          <animate
            attributeName="opacity"
            values="0;1;1;0"
            keyTimes="0;.05;.955;1"
            dur="3.8s"
            repeatCount="indefinite"
          />
        </g>

        <g transform="translate(191.5 85.5)">
          <circle
            className="az-pulse"
            r="18"
            fill="none"
            stroke="var(--primary)"
            strokeWidth={1.4}
            opacity="0"
          >
            <animate
              attributeName="r"
              values="10;10;15;24"
              keyTimes="0;.82;.9;1"
              dur="3.8s"
              repeatCount="indefinite"
            />
            <animate
              attributeName="opacity"
              values="0;0;.32;0"
              keyTimes="0;.82;.9;1"
              dur="3.8s"
              repeatCount="indefinite"
            />
          </circle>
          <circle r="11" fill="var(--primary)" />
        </g>
      </g>
    </svg>
  );
}
