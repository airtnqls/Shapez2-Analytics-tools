"use client";

import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Button({ className, variant = "default", size = "md", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "ghost" | "danger" | "outline"; size?: "xs" | "sm" | "md" | "icon" }) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md border border-transparent font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color-mix(in_srgb,var(--accent)_24%,transparent)] disabled:pointer-events-none disabled:opacity-40",
        size === "xs" && "h-7 px-2 text-[11px]",
        size === "sm" && "h-8 px-2.5 text-xs",
        size === "md" && "h-9 px-3 text-sm",
        size === "icon" && "h-8 w-8 p-0",
        variant === "default" && "border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--text)] hover:bg-[var(--surface-3)]",
        variant === "primary" && "border-[var(--accent)] bg-[var(--accent)] text-[var(--accent-contrast)] hover:bg-[var(--accent-hover)]",
        variant === "ghost" && "text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
        variant === "danger" && "bg-[var(--danger)] text-white hover:brightness-110",
        variant === "outline" && "border border-[var(--border-strong)] bg-transparent text-[var(--text)] hover:bg-[var(--surface-2)]",
        className,
      )}
      {...props}
    />
  );
}

export function IconButton({ label, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return <Button size="icon" variant="ghost" aria-label={label} title={label} {...props}>{children}</Button>;
}

export function Badge({ children, tone = "neutral", className }: { children: ReactNode; tone?: "neutral" | "positive" | "negative" | "unknown" | "accent"; className?: string }) {
  return <span className={cn(
    "inline-flex h-5 items-center rounded-[4px] border px-1.5 text-[10px] font-semibold leading-none tracking-[.04em]",
    tone === "neutral" && "border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--muted)]",
    tone === "positive" && "border-emerald-500/35 bg-emerald-500/10 text-emerald-400",
    tone === "negative" && "border-rose-500/35 bg-rose-500/10 text-rose-400",
    tone === "unknown" && "border-amber-500/35 bg-amber-500/10 text-amber-400",
    tone === "accent" && "border-[color-mix(in_srgb,var(--accent)_42%,transparent)] bg-[color-mix(in_srgb,var(--accent)_12%,transparent)] text-[var(--accent-strong)]",
    className,
  )}>{children}</span>;
}

export function SectionTitle({ icon, title, action, subtitle }: { icon?: ReactNode; title: string; action?: ReactNode; subtitle?: ReactNode }) {
  return <div className="flex min-h-9 items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--surface-1)] px-3">
    <div className="min-w-0">
      <div className="flex items-center gap-2 text-xs font-semibold">{icon}<span className="truncate">{title}</span></div>
      {subtitle ? <div className="truncate text-[10px] text-[var(--muted)]">{subtitle}</div> : null}
    </div>
    {action ? <div className="flex shrink-0 items-center gap-1">{action}</div> : null}
  </div>;
}

export function Panel({ children, className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <section className={cn("min-h-0 overflow-hidden border border-[var(--border)] bg-[var(--surface-1)]", className)} {...props}>{children}</section>;
}

export function Metric({ label, value, detail }: { label: string; value: ReactNode; detail?: ReactNode }) {
  return <div className="min-w-0 border-l-2 border-[var(--border-strong)] px-2 py-1.5">
    <div className="truncate text-[9px] font-semibold uppercase tracking-[.1em] text-[var(--muted)]">{label}</div>
    <div className="mt-0.5 truncate text-sm font-semibold text-[var(--text)]">{value}</div>
    {detail ? <div className="mt-0.5 truncate text-[10px] text-[var(--muted)]">{detail}</div> : null}
  </div>;
}

export function Segmented({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("inline-flex items-center gap-px rounded-md border border-[var(--border)] bg-[var(--surface-0)] p-0.5", className)}>{children}</div>;
}

export function SegmentButton({ active, className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return <button type="button" className={cn(
    "h-7 rounded px-2.5 text-[11px] font-medium text-[var(--muted)] transition-colors hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
    active && "bg-[var(--surface-1)] text-[var(--accent-strong)]",
    className,
  )} {...props} />;
}

export function DefinitionRow({ label, value, mono = false, tone }: { label: ReactNode; value: ReactNode; mono?: boolean; tone?: "positive" | "negative" | "unknown" }) {
  return <div className="grid min-h-8 grid-cols-[minmax(96px,.8fr)_minmax(0,1.2fr)] items-center gap-3 border-b border-[var(--border)] px-3 py-1.5 last:border-b-0">
    <div className="text-[11px] text-[var(--muted)]">{label}</div>
    <div className={cn("min-w-0 break-words text-right text-[11px] font-medium", mono && "font-mono", tone === "positive" && "text-emerald-400", tone === "negative" && "text-rose-400", tone === "unknown" && "text-amber-400")}>{value}</div>
  </div>;
}
