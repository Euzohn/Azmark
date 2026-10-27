import { cn } from "@/lib/utils";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-lg border border-border bg-card px-3.5 text-base text-foreground outline-none transition-colors duration-150 placeholder:text-muted-foreground/80 focus:border-primary/50 focus:ring-2 focus:ring-ring/25 disabled:opacity-50 md:h-10 md:text-sm",
        className,
      )}
      {...props}
    />
  );
}
