import { useState } from "react";
import { ChevronDown, Gauge } from "lucide-react";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import type { MetricKey } from "@/types/contextSwitch";
import { ConfidenceBar, Panel, SectionTitle, Sparkline } from "./primitives";
import { cn } from "@/lib/utils";

const ROWS: Array<{ key: MetricKey; label: string; fmt: (v: number) => string; invert?: boolean }> = [
  { key: "ambientNoise", label: "Ambient noise", fmt: (v) => `${Math.round(30 + v * 60)} dB`, invert: true },
  { key: "voice", label: "Voice recognition", fmt: (v) => `${Math.round(v * 100)}%` },
  { key: "face", label: "Face tracking", fmt: (v) => `${Math.round(v * 100)}%` },
  { key: "hand", label: "Hand tracking", fmt: (v) => `${Math.round(v * 100)}%` },
  { key: "imu", label: "IMU health", fmt: (v) => `${Math.round(v * 100)}%` },
  { key: "latency", label: "Backend latency", fmt: (v) => `${Math.round(v)} ms`, invert: true },
];

export function ReliabilityMonitor({ defaultOpen = false }: { defaultOpen?: boolean }) {
  const { state } = useContextSwitchState();
  const [open, setOpen] = useState(defaultOpen);

  return (
    <Panel>
      <button onClick={() => setOpen((o) => !o)} className="w-full" aria-expanded={open}>
        <SectionTitle icon={<Gauge className="size-3.5" />} right={<ChevronDown className={cn("size-3.5 text-muted-foreground transition-transform duration-200", open && "rotate-180")} />}>
          Sensor readings
        </SectionTitle>
      </button>
      {open && (
        <ul className="space-y-2.5 animate-rise">
          {ROWS.map((r) => {
            const m = state.metrics[r.key];
            const bar = m.value === null ? null : r.key === "latency" ? Math.min(1, m.value / 150) : m.value;
            return (
              <li key={r.key} className="grid grid-cols-[1fr_auto_auto] items-center gap-x-3 text-[11.5px]">
                <div className="min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">{r.label}</span>
                    <span className="flex items-center gap-1.5 font-mono tabular-nums">
                      {m.value === null ? <span className="text-subtle">unavailable</span> : r.fmt(m.value)}
                    </span>
                  </div>
                  <ConfidenceBar value={r.invert && bar !== null ? 1 - bar : bar} tone="ok" className="mt-1" />
                </div>
                <Sparkline data={m.history} className={m.source === "unavailable" ? "opacity-30" : ""} />
                <span
                  title={m.source === "measured" ? "Measured by sensor" : m.source === "simulated" ? "Demo simulation value" : "Not available"}
                  className={cn("w-8 text-right font-mono text-[9px] uppercase tracking-wider", m.source === "measured" ? "text-success" : m.source === "simulated" ? "text-warning" : "text-subtle")}
                >
                  {m.source === "measured" ? "live" : m.source === "simulated" ? "sim" : "n/a"}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
}
