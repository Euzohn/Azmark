import { cn } from "@/lib/utils";

interface StatProps {
  label: string;
  value: string | number;
  hint?: string;
  className?: string;
}

/**
 * Compact metric block: a tabular-figures value over a muted label.
 * Used in the dashboard hero strip and statistics, replacing the old
 * equal-height tile walls.
 */
export function Stat({ label, value, hint, className }: StatProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="font-display text-2xl font-semibold tracking-tight tabular-nums text-foreground">
        {value}
      </div>
      <div className="text-xs text-muted-foreground">{label}</div>
      {hint ? <div className="text-[11px] text-muted-foreground/70">{hint}</div> : null}
    </div>
  );
}
