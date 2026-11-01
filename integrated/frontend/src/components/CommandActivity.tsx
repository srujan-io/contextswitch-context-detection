import { Activity, Check, Clock, X, Ban, FlaskConical } from "lucide-react";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import { MODALITY_ICON, MODALITY_SHORT, fmtTime } from "@/lib/modalities";
import type { CommandStatus } from "@/types/contextSwitch";
import { Panel, SectionTitle, StatusDot } from "./primitives";
import { cn } from "@/lib/utils";

const STATUS: Record<CommandStatus, { label: string; cls: string; Icon: typeof Check }> = {
  detected: { label: "Detected", cls: "text-primary", Icon: Activity },
  executed: { label: "Executed", cls: "text-success", Icon: Check },
  simulated: { label: "Simulated", cls: "text-warning", Icon: FlaskConical },
  pending: { label: "Pending", cls: "text-muted-foreground", Icon: Clock },
  failed: { label: "Failed", cls: "text-destructive", Icon: X },
  rejected: { label: "Rejected", cls: "text-muted-foreground", Icon: Ban },
};

export function CommandActivity({ limit = 6 }: { limit?: number }) {
  const { state } = useContextSwitchState();
  const live = state.lastEventAt !== null && !state.paused;
  return (
    <Panel>
      <SectionTitle
        icon={<Activity className="size-3.5" />}
        right={<span className="flex items-center gap-1.5 text-[10px] text-muted-foreground"><StatusDot tone={live ? "active" : "off"} pulse={live} />{state.paused ? "Paused" : "Live"}</span>}
      >
        Live Activity
      </SectionTitle>
      {state.commands.length === 0 ? (
        <p className="py-4 text-center text-[11.5px] text-muted-foreground">
          {state.connection === "connected" ? "Waiting for interpreted commands…" : "No activity — backend not connected."}
        </p>
      ) : (
        <ul className="-mx-1 divide-y divide-border">
          {state.commands.slice(0, limit).map((c) => {
            const Icon = MODALITY_ICON[c.source];
            const s = STATUS[c.status];
            return (
              <li key={c.id} className="flex items-center gap-2 px-1 py-1.5 text-[11.5px] animate-rise">
                <Icon className="size-3.5 shrink-0 text-muted-foreground" strokeWidth={1.75} />
                <span className="w-9 shrink-0 font-mono text-[10px] text-muted-foreground">{MODALITY_SHORT[c.source]}</span>
                <span className="min-w-0 flex-1 truncate font-mono text-[11px]">
                  {c.action}
                  {c.target && <span className="text-muted-foreground"> ({c.target})</span>}
                </span>
                <span className={cn("flex shrink-0 items-center gap-1 text-[10.5px]", s.cls)}>
                  <s.Icon className={cn("size-3", c.status === "pending" && "animate-pulse")} />
                  {s.label}
                </span>
                <span className="hidden shrink-0 font-mono text-[10px] text-subtle min-[380px]:inline">{fmtTime(c.ts)}</span>
              </li>
            );
          })}
        </ul>
      )}
      {state.source === "simulation" && state.commands.length > 0 && (
        <p className="mt-2 text-[10px] text-muted-foreground">Simulated commands are never sent to KiCanvas.</p>
      )}
      {state.commands.some((command) => command.status === "detected") && (
        <p className="mt-2 text-[10px] text-muted-foreground">Detected CV actions are sensor events, not browser execution results.</p>
      )}
    </Panel>
  );
}
