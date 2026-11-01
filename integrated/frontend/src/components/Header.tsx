import { Link } from "@tanstack/react-router";
import { Maximize2, Minimize2, Pause, Play, Settings as SettingsIcon } from "lucide-react";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import { SimBadge, StatusDot } from "./primitives";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./ThemeToggle";

const CONN = {
  connected: { label: "Connected", tone: "ok" as const },
  reconnecting: { label: "Reconnecting", tone: "warn" as const },
  disconnected: { label: "Disconnected", tone: "off" as const },
};

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("grid size-7 place-items-center rounded-md border border-border bg-surface-raised", className)}>
      <svg viewBox="0 0 24 24" className="size-4 text-primary" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M4 8h10l-3-3M20 16H10l3 3" />
      </svg>
    </div>
  );
}

export function Header({ onSettings, variant }: { onSettings?: () => void; variant: "popup" | "dashboard" }) {
  const { state, togglePause } = useContextSwitchState();
  const c = CONN[state.connection];
  const btn = "grid size-7 place-items-center rounded-md border border-border bg-surface-raised text-muted-foreground transition-colors duration-150 hover:text-foreground hover:border-primary/40";
  return (
    <header className="flex items-center gap-2.5">
      <Logo />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h1 className="font-display text-[15px] font-semibold leading-none tracking-tight">ContextSwitch</h1>
          {state.source === "simulation" && <SimBadge />}
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="truncate">{state.source === "backend" ? "CV telemetry / read-only" : "Hands-free control"}</span>
          <span className="text-subtle">·</span>
          <StatusDot tone={c.tone} pulse={state.connection === "connected"} />
          <span>{c.label}</span>
        </div>
      </div>
      <button
        onClick={togglePause}
        disabled={state.source === "backend"}
        className={cn(btn, state.paused && "border-warning/50 text-warning")}
        aria-label={state.paused ? "Resume input" : "Pause input"}
        title={state.source === "backend" ? "Live CV telemetry is read-only" : state.paused ? "Resume" : "Pause"}
      >
        {state.paused ? <Play className="size-3.5" /> : <Pause className="size-3.5" />}
      </button>
      <ThemeToggle className={btn} />
      {onSettings && (
        <button onClick={onSettings} className={btn} aria-label="Settings" title="Settings">
          <SettingsIcon className="size-3.5" />
        </button>
      )}
      {variant === "popup" ? (
        <Link to="/dashboard" className={btn} aria-label="Open dashboard" title="Expanded dashboard">
          <Maximize2 className="size-3.5" />
        </Link>
      ) : (
        <Link to="/" className={btn} aria-label="Back to popup" title="Popup view">
          <Minimize2 className="size-3.5" />
        </Link>
      )}
    </header>
  );
}
