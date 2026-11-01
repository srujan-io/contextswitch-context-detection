import { PauseCircle, WifiOff } from "lucide-react";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import { MODALITY_ICON, MODALITY_LABEL, fmtTime, pct } from "@/lib/modalities";
import { ConfidenceBar, StatusDot } from "./primitives";

export function ActiveModalityCard() {
  const { state } = useContextSwitchState();
  const { agent, connection, paused, modalities } = state;
  const active = agent.active;
  const conf = active ? modalities.find((m) => m.id === active)?.confidence ?? null : null;

  if (connection === "disconnected" && state.source === "backend") {
    return (
      <section className="glass rounded-lg p-3.5">
        <div className="flex items-start gap-3">
          <WifiOff className="mt-0.5 size-4 text-muted-foreground" />
          <div className="text-[12px] leading-relaxed text-muted-foreground">
            <p className="text-[13px] font-medium text-foreground">Not connected</p>
            The live sensor stream isn't connected. Check the CV feature flag and service, or turn on Demo Mode in settings.
          </div>
        </div>
      </section>
    );
  }

  const Icon = active ? MODALITY_ICON[active] : null;

  return (
    <section className="glass rounded-lg p-3.5">
      <div className="flex items-center justify-between text-[10.5px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <StatusDot tone={active && !paused ? "active" : "off"} pulse={!!active && !paused} />
          {state.source === "backend" ? "CV event stream" : paused ? "Paused" : "Now controlling with"}
        </span>
        <span className={agent.selectedBy === "manual" ? "text-warning" : ""}>
          {agent.selectedBy === "manual" ? "Your choice" : "Chosen automatically"}
        </span>
      </div>

      <div key={active ?? "none"} className="mt-2 flex items-center gap-3 animate-rise">
        {Icon && <Icon className="size-6 text-primary" strokeWidth={1.5} />}
        <p className="font-display min-w-0 flex-1 truncate text-[23px] font-medium leading-tight tracking-tight">{active ? MODALITY_LABEL[active] : "Waiting for input"}</p>
        <p className="font-mono text-[18px] tabular-nums text-foreground">{pct(conf)}</p>
      </div>
      <ConfidenceBar value={conf} className="mt-2.5" />

      {paused ? (
        <p className="mt-2.5 flex items-center gap-1.5 text-[11.5px] text-muted-foreground"><PauseCircle className="size-3.5" />No commands are sent while paused.</p>
      ) : agent.reason ? (
        <p key={agent.lastSwitch ?? 0} className="mt-2.5 text-[11.5px] leading-relaxed text-muted-foreground animate-rise">
          {agent.reason}
          {agent.lastSwitch && <span className="ml-1.5 font-mono text-[10px] text-subtle">{fmtTime(agent.lastSwitch)}</span>}
        </p>
      ) : null}
    </section>
  );
}
