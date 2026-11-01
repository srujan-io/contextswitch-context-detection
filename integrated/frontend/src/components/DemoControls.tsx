import { FlaskConical } from "lucide-react";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import type { DemoScenario } from "@/types/contextSwitch";
import { Panel, SectionTitle, SimBadge } from "./primitives";
import { cn } from "@/lib/utils";

const SCENARIOS: Array<{ id: DemoScenario; label: string }> = [
  { id: "normal", label: "Normal" },
  { id: "noise", label: "Noisy room" },
  { id: "camera", label: "Camera blocked" },
  { id: "mic", label: "No mic" },
  { id: "recovery", label: "Recovered" },
];

export function DemoControls({ onEnable, compact }: { onEnable?: () => void; compact?: boolean }) {
  const { state, runScenario } = useContextSwitchState();

  if (state.source !== "simulation") {
    if (compact) {
      return (
        <button onClick={onEnable} className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground">
          <FlaskConical className="size-3.5" />Try Demo Mode
        </button>
      );
    }
    return (
      <Panel>
        <SectionTitle icon={<FlaskConical className="size-3.5" />}>Demo Mode</SectionTitle>
        <p className="text-[11.5px] text-muted-foreground">Simulate difficult conditions without sending real actions.</p>
        {onEnable && <button onClick={onEnable} className="mt-2 rounded-md border border-border bg-surface-raised px-2.5 py-1 text-[11.5px] hover:border-primary/40">Turn on in settings</button>}
      </Panel>
    );
  }

  const chips = (
    <div className="flex flex-wrap gap-1">
      {SCENARIOS.map(({ id, label }) => (
        <button
          key={id}
          onClick={() => runScenario(id)}
          aria-pressed={state.scenario === id}
          className={cn(
            "rounded-full border px-2 py-0.5 text-[10.5px] transition-colors duration-150",
            state.scenario === id ? "border-warning/50 bg-warning/15 text-foreground" : "border-border text-muted-foreground hover:text-foreground",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );

  if (compact) {
    return (
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[10.5px] text-muted-foreground">Simulate a condition</span>
          <SimBadge />
        </div>
        {chips}
      </div>
    );
  }
  return (
    <Panel>
      <SectionTitle icon={<FlaskConical className="size-3.5" />} right={<SimBadge />}>Demo scenarios</SectionTitle>
      {chips}
      <p className="mt-2 text-[10.5px] text-muted-foreground">Simulation only — nothing is sent to KiCanvas.</p>
    </Panel>
  );
}
