import { toast } from "sonner";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import { MODALITY_ICON, MODALITY_LABEL, MODALITY_SHORT, STATUS_LABEL, pct } from "@/lib/modalities";
import { MODALITY_IDS } from "@/types/contextSwitch";
import { cn } from "@/lib/utils";

/** Compact 4-up modality row for the popup. Tap to choose when in Manual mode. */
export function ModalityStrip() {
  const { state, selectModality } = useContextSwitchState();
  const manual = state.mode === "manual" && state.source !== "backend";
  const list = state.modalities.length ? state.modalities : MODALITY_IDS.map((id) => ({ id, available: false, confidence: null, status: "unavailable" as const }));

  return (
    <div className="grid grid-cols-4 overflow-hidden rounded-lg border border-border">
      {list.map((m, i) => {
        const Icon = MODALITY_ICON[m.id];
        const isActive = state.agent.active === m.id;
        return (
          <button
            key={m.id}
            type="button"
            disabled={!manual}
            title={`${MODALITY_LABEL[m.id]} — ${STATUS_LABEL[m.status]}`}
            onClick={() => {
              if (!m.available) { toast.error(`${MODALITY_LABEL[m.id]} isn't available right now`); return; }
              selectModality(m.id);
            }}
            className={cn(
              "relative flex flex-col items-center gap-1 bg-surface py-2.5 transition-colors duration-150 disabled:cursor-default",
              i > 0 && "border-l border-border",
              isActive && "bg-surface-raised",
              manual && m.available && !isActive && "hover:bg-surface-raised",
              !m.available && "opacity-45",
            )}
          >
            {isActive && <span className="absolute inset-x-0 top-0 h-0.5 bg-primary" />}
            <Icon className={cn("size-4", isActive ? "text-primary" : "text-muted-foreground")} strokeWidth={1.6} />
            <span className={cn("text-[10px] font-medium tracking-wide", isActive ? "text-foreground" : "text-muted-foreground")}>{MODALITY_SHORT[m.id]}</span>
            <span className="font-mono text-[10px] tabular-nums text-subtle">{m.available ? pct(m.confidence) : "off"}</span>
          </button>
        );
      })}
    </div>
  );
}
