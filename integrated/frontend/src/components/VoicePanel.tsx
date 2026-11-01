import { AlertTriangle, Mic, MicOff } from "lucide-react";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import { pct } from "@/lib/modalities";
import { Panel, SectionTitle, Waveform } from "./primitives";
import { cn } from "@/lib/utils";

export function VoicePanel() {
  const { state, confirmVoice } = useContextSwitchState();
  const { voice } = state;
  const voiceActive = state.agent.active === "voice";
  const phase = voice.mic === "unavailable" ? "Unavailable" : voiceActive ? (voice.phase === "processing" ? "Processing" : "Listening") : "Idle";

  return (
    <Panel>
      <SectionTitle
        icon={voice.mic === "available" ? <Mic className="size-3.5" /> : <MicOff className="size-3.5" />}
        right={<span className={cn("flex items-center gap-1.5 text-[10.5px]", phase === "Listening" ? "text-primary" : "text-muted-foreground")}>
          {phase === "Listening" && <Waveform active={!state.paused} bars={4} />}{phase}
        </span>}
      >
        Voice
      </SectionTitle>

      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11.5px]">
        <span className="text-muted-foreground">Heard</span>
        <span className="truncate">{voice.transcript ? `“${voice.transcript}”` : <span className="text-muted-foreground">—</span>}</span>
        <span className="text-muted-foreground">Intent</span>
        <span className="flex items-center justify-between gap-2">
          <span className="truncate font-mono text-[11px] text-primary">{voice.intent ?? "—"}</span>
          <span className="font-mono text-[10px] text-muted-foreground">{pct(voice.confidence)}</span>
        </span>
      </div>

      {voice.pendingConfirmation && (
        <div className="mt-3 rounded-lg border border-warning/35 bg-warning/10 p-2.5 animate-rise">
          <p className="flex items-start gap-1.5 text-[11.5px]">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" />
            <span><span className="font-medium text-warning">Confirmation required.</span> {voice.pendingConfirmation.prompt}</span>
          </p>
          <div className="mt-2 flex gap-2">
            <button onClick={() => confirmVoice(true)} className="flex-1 rounded-md bg-primary px-2 py-1 text-[11.5px] font-medium text-primary-foreground transition-opacity hover:opacity-90">Confirm</button>
            <button onClick={() => confirmVoice(false)} className="flex-1 rounded-md border border-border bg-surface-raised px-2 py-1 text-[11.5px] text-foreground transition-colors hover:border-destructive/50 hover:text-destructive">Reject</button>
          </div>
          <p className="mt-1.5 text-[10px] text-muted-foreground">Ambiguous commands are held until you decide.</p>
        </div>
      )}
    </Panel>
  );
}
