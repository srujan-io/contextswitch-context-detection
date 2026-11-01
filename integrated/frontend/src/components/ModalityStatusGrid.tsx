import { toast } from "sonner";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import { MODALITY_ICON, MODALITY_LABEL, MODALITY_METRIC_LABEL, STATUS_LABEL, pct, statusTone } from "@/lib/modalities";
import { MODALITY_IDS } from "@/types/contextSwitch";
import { ConfidenceBar, StatusDot, Waveform } from "./primitives";
import { cn } from "@/lib/utils";

export function ModalityStatusGrid({ className }: { className?: string }) {
  const { state, selectModality } = useContextSwitchState();
  const manual = state.mode === "manual" && state.source !== "backend";

  if (state.modalities.length === 0 && state.source === "simulation") {
    return (
      <div className={cn("grid grid-cols-2 gap-2", className)}>
        {MODALITY_IDS.map((id) => <div key={id} className="glass h-[80px] animate-pulse rounded-lg" />)}
      </div>
    );
  }

  const modalities = state.modalities.length > 0
    ? state.modalities
    : MODALITY_IDS.map((id) => ({ id, status: "unavailable" as const, available: false, confidence: null }));

  return (
    <div className={cn("grid grid-cols-2 gap-2", className)}>
      {modalities.map((m) => {
        const Icon = MODALITY_ICON[m.id];
        const isActive = state.agent.active === m.id;
        const tone = isActive ? "active" : statusTone(m.status);
        const status = isActive ? (m.id === "voice" ? "Listening" : "Active") : STATUS_LABEL[m.status];
        const onClick = () => {
          if (!manual) return;
          if (!m.available) { toast.error(`${MODALITY_LABEL[m.id]} is unavailable`); return; }
          selectModality(m.id);
        };
        return (
          <button
            key={m.id}
            type="button"
            onClick={onClick}
            disabled={!manual}
            aria-pressed={isActive}
            className={cn(
              "glass group rounded-lg p-3 text-left transition-all duration-200 disabled:cursor-default",
              isActive && "border-primary/50 glow-active",
              !m.available && "opacity-60",
              manual && m.available && !isActive && "hover:border-primary/30 cursor-pointer",
            )}
          >
            <div className="flex items-center justify-between">
              <Icon className={cn("size-4", isActive ? "text-primary" : "text-muted-foreground")} strokeWidth={1.75} />
              {m.id === "voice" && isActive && !state.paused ? <Waveform active /> :
               m.id === "head" && isActive ? <span className="relative h-3.5 w-4 overflow-hidden rounded-sm border border-primary/40"><span className="absolute inset-x-0 top-1/2 h-px bg-primary animate-scan" /></span> :
               <StatusDot tone={tone} pulse={isActive} />}
            </div>
            <p className="mt-2 text-[12.5px] font-medium">{MODALITY_LABEL[m.id]}</p>
            <div className="mt-0.5 flex items-center justify-between text-[10.5px]">
              <span className={cn(isActive ? "text-primary" : tone === "off" ? "text-muted-foreground" : tone === "warn" ? "text-warning" : "text-success")}>{status}</span>
              <span className="font-mono tabular-nums text-muted-foreground" title={MODALITY_METRIC_LABEL[m.id]}>{pct(m.confidence)}</span>
            </div>
            <ConfidenceBar value={m.confidence} tone={isActive ? "active" : "ok"} className="mt-1.5" />
          </button>
        );
      })}
    </div>
  );
}
