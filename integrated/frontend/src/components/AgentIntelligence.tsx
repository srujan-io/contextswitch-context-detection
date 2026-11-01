import { BrainCircuit } from "lucide-react";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import { MODALITY_LABEL, fmtTime, pct } from "@/lib/modalities";
import type { DecisionKind } from "@/types/contextSwitch";
import { Panel, SectionTitle } from "./primitives";
import { cn } from "@/lib/utils";

const KIND_DOT: Record<DecisionKind, string> = {
  selected: "bg-primary",
  switched: "bg-primary",
  stable: "bg-success",
  observation: "bg-muted-foreground",
  override: "bg-warning",
  warning: "bg-destructive",
};

export function AgentIntelligence({ timelineLimit = 5 }: { timelineLimit?: number }) {
  const { state, setMode } = useContextSwitchState();
  const { agent, mode, decisions } = state;

  return (
    <Panel>
      <SectionTitle
        icon={<BrainCircuit className="size-3.5" />}
        right={
          <div role="radiogroup" aria-label="Selection mode" className="flex rounded-md border border-border bg-background/60 p-0.5 text-[11px]">
            {(["auto", "manual"] as const).map((m) => (
              <button
                key={m}
                role="radio"
                aria-checked={mode === m}
                disabled={state.source === "backend"}
                onClick={() => setMode(m)}
                className={cn("rounded px-2.5 py-0.5 capitalize transition-colors duration-150", mode === m ? "bg-surface-raised text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}
              >
                {m === "auto" ? "Automatic" : "Manual"}
              </button>
            ))}
          </div>
        }
      >
        Why this input
      </SectionTitle>

      <dl className="grid grid-cols-3 gap-2 text-[11px]">
        <div><dt className="text-muted-foreground">Selected</dt><dd className="mt-0.5 font-medium">{agent.active ? MODALITY_LABEL[agent.active] : "—"}</dd></div>
        <div><dt className="text-muted-foreground">Last switch</dt><dd className="mt-0.5 font-mono">{agent.lastSwitch ? fmtTime(agent.lastSwitch) : "—"}</dd></div>
        <div><dt className="text-muted-foreground">Reliability</dt><dd className="mt-0.5 font-mono text-primary">{pct(agent.reliability)}</dd></div>
      </dl>

      {mode === "manual" && state.source !== "backend" && (
        <p className="mt-2.5 rounded-md border border-warning/30 bg-warning/10 px-2 py-1.5 text-[11px] text-warning">
          Manual mode — tap an available modality above to override the agent.
        </p>
      )}
      {state.source === "backend" && (
        <p className="mt-2.5 rounded-md border border-border bg-background/60 px-2 py-1.5 text-[11px] text-muted-foreground">
          Live integration is read-only; agent selection controls are not connected.
        </p>
      )}

      <ol className="mt-3 space-y-1.5 border-l border-border pl-3">
        {decisions.length === 0 && <li className="text-[11px] text-muted-foreground">No agent decisions yet.</li>}
        {decisions.slice(0, timelineLimit).map((d) => (
          <li key={d.id} className="relative flex gap-2 text-[11.5px] animate-rise">
            <span className={cn("absolute -left-[15.5px] top-1.5 size-1.5 rounded-full", KIND_DOT[d.kind])} />
            <span className="shrink-0 font-mono text-[10.5px] text-muted-foreground tabular-nums">{fmtTime(d.ts)}</span>
            <span className={cn(d.kind === "switched" || d.kind === "override" ? "text-foreground" : "text-muted-foreground")}>{d.message}</span>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
