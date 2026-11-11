"use client";

/**
 * Safe, theme-conformant Markdown rendering for assistant content.
 *
 * react-markdown escapes raw HTML by default, so embedded markup from the
 * model (or from untrusted content quoted inside the message) can never
 * become DOM elements — it renders as text (spec #70). Its default URL
 * transform also drops non-http(s) protocols, so `javascript:` links die.
 * All styling uses the palette tokens so it survives light / dark themes.
 */

import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

function MarkdownInner({ className, content }: { className?: string; content: string }) {
  return (
    <div className={cn("overflow-hidden text-sm", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mb-2 mt-1 text-lg font-semibold leading-snug first:mt-0">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-1.5 mt-3 text-base font-semibold leading-snug first:mt-0">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-1 mt-2.5 text-sm font-semibold leading-snug first:mt-0">{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 className="mb-1 mt-2 text-sm font-semibold leading-snug first:mt-0">{children}</h4>
          ),
          h5: ({ children }) => (
            <h5 className="mb-1 mt-2 text-sm font-medium leading-snug first:mt-0">{children}</h5>
          ),
          h6: ({ children }) => (
            <h6 className="mb-1 mt-2 text-sm font-medium leading-snug first:mt-0">{children}</h6>
          ),
          p: ({ children }) => <p className="mb-2 leading-relaxed last:mb-0">{children}</p>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="break-words text-primary underline decoration-primary/40 underline-offset-2 transition-colors hover:decoration-primary"
            >
              {children}
            </a>
          ),
          ul: ({ children }) => (
            <ul className="mb-2 list-disc space-y-0.5 pl-5 last:mb-0">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 list-decimal space-y-0.5 pl-5 last:mb-0">{children}</ol>
          ),
          li: ({ children, className }) => (
            <li className={cn("pl-0.5 leading-relaxed", className?.includes("task-list-item") && "list-none")}>
              {children}
            </li>
          ),
          input: ({ checked, disabled }) => (
            <input
              type="checkbox"
              checked={checked}
              disabled={disabled}
              readOnly
              className="mr-1.5 translate-y-px accent-primary"
            />
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-primary/50 pl-3 text-muted-foreground last:mb-0">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-3 border-border/60" />,
          code: ({ className, children }) => {
            // Fenced blocks carry a language class; inline code never contains
            // a newline (CommonMark folds them to spaces), so multi-line text
            // without a language class is still a block.
            const text = Array.isArray(children) ? children.join("") : children;
            const isBlock =
              Boolean(className) || (typeof text === "string" && text.includes("\n"));
            return (
              <code
                className={cn(
                  "font-mono text-[0.85em]",
                  !isBlock && "rounded bg-black/10 px-1.5 py-0.5 dark:bg-white/10",
                )}
              >
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre className="my-2 overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-black/10 p-3 font-mono text-xs leading-relaxed dark:bg-white/10">
              {children}
            </pre>
          ),
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="whitespace-nowrap border border-border/70 px-2 py-1 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-border/70 px-2 py-1 align-top">{children}</td>
          ),
          img: ({ src, alt }) => (
            // eslint-disable-next-line @next/next/no-img-element -- arbitrary remote URLs from model output; next/image would need remotePatterns for every domain
            <img src={src} alt={alt} loading="lazy" className="my-2 max-h-64 max-w-full rounded-lg" />
          ),
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          del: ({ children }) => <del className="opacity-70">{children}</del>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export const Markdown = memo(MarkdownInner);