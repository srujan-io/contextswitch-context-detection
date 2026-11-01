import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Tone } from "@/lib/modalities";

export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cn("glass rounded-lg p-3", className)}>{children}</section>;
}

export function SectionTitle({ icon, children, right }: { icon?: ReactNode; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-2.5 flex items-center justify-between gap-2">
      <h2 className="flex items-center gap-1.5 text-[12px] font-medium text-foreground">
        {icon}
        {children}
      </h2>
      {right}
    </div>
  );
}

const toneDot: Record<Tone, string> = {
  active: "bg-primary",
  ok: "bg-success",
  warn: "bg-warning",
  off: "bg-muted-foreground/40",
};

export function StatusDot({ tone, pulse }: { tone: Tone; pulse?: boolean }) {
  return (
    <span className="relative inline-flex size-2 shrink-0">
      {pulse && <span className={cn("absolute inset-0 rounded-full animate-ping-soft", toneDot[tone])} />}
      <span className={cn("relative size-2 rounded-full", toneDot[tone])} />
    </span>
  );
}

export function ConfidenceBar({ value, tone = "active", className }: { value: number | null; tone?: Tone; className?: string }) {
  const color = value === null ? "bg-transparent" : value < 0.6 ? "bg-destructive/80" : tone === "active" ? "bg-brand" : "bg-foreground/50";
  return (
    <div className={cn("h-1 w-full overflow-hidden rounded-full bg-subtle/60", className)}>
      <div className={cn("h-full rounded-full transition-[width] duration-500 ease-out", color)} style={{ width: `${Math.round((value ?? 0) * 100)}%` }} />
    </div>
  );
}

export function Waveform({ active, bars = 5, className }: { active: boolean; bars?: number; className?: string }) {
  return (
    <span className={cn("inline-flex h-3.5 items-center gap-[2px]", className)} aria-hidden>
      {Array.from({ length: bars }).map((_, i) => (
        <span
          key={i}
          className={cn("w-[2px] rounded-full bg-primary h-full", active ? "animate-wave" : "scale-y-[0.3] opacity-40")}
          style={{ animationDelay: `${i * 0.12}s` }}
        />
      ))}
    </span>
  );
}

export function Sparkline({ data, className }: { data: number[]; className?: string }) {
  if (data.length < 2) return <div className={cn("h-5 w-16", className)} />;
  const max = Math.max(...data, 1e-6);
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * 64},${20 - (v / max) * 18 - 1}`).join(" ");
  return (
    <svg viewBox="0 0 64 20" className={cn("h-5 w-16 text-primary", className)} aria-hidden>
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function SimBadge({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded border border-warning/40 px-1.5 py-px font-mono text-[9.5px] text-warning", className)}>
      <span className="size-1.5 rounded-full bg-warning" />
      Demo data
    </span>
  );
}

export function Chip({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("rounded-md border border-border bg-surface-raised px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground", className)}>{children}</span>;
}
