import { cn } from "@/lib/utils";

export function Textarea({
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "w-full rounded-xl border border-border bg-card px-3.5 py-2 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-muted-foreground/80 focus:border-primary/50 focus:ring-2 focus:ring-ring/25 disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}
