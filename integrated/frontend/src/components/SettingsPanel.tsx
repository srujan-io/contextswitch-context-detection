import { useEffect, useState, type ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { MODALITY_LABEL } from "@/lib/modalities";
import { MODALITY_IDS, type ModalityId, type Settings } from "@/types/contextSwitch";

function Row({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <div className="min-w-0">
        <p className="text-[12.5px]">{label}</p>
        {hint && <p className="text-[10.5px] text-muted-foreground">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}
const field = "rounded-md border border-input bg-background/60 px-2 py-1 text-[12px] outline-none focus:border-primary/60 focus:ring-2 focus:ring-ring/30";

export function SettingsPanel({ onBack }: { onBack: () => void }) {
  const { state, saveSettings, storageKind } = useContextSwitchState();
  const [draft, setDraft] = useState<Settings>(state.settings);
  useEffect(() => setDraft(state.settings), [state.settings]);
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const dirty = JSON.stringify(draft) !== JSON.stringify(state.settings);
  const validWs = /^wss?:\/\/.+/.test(draft.endpoint);

  const save = async () => {
    if (!validWs) { toast.error("Endpoint must start with ws:// or wss://"); return; }
    await saveSettings(draft);
    toast.success("Settings saved");
  };

  return (
    <div className="flex h-full flex-col animate-rise">
      <div className="mb-3 flex items-center gap-2">
        <button onClick={onBack} className="grid size-7 place-items-center rounded-md border border-border bg-surface-raised text-muted-foreground hover:text-foreground" aria-label="Back"><ArrowLeft className="size-3.5" /></button>
        <h2 className="font-display text-[15px] font-semibold tracking-tight">Settings</h2>
        <span className="ml-auto font-mono text-[9.5px] text-muted-foreground">{storageKind === "chrome.storage" ? "chrome.storage" : "local mock storage"}</span>
      </div>

      <div className="glass flex-1 divide-y divide-border overflow-y-auto rounded-lg px-3.5">
        <div className="py-2.5">
          <label className="text-[12.5px]" htmlFor="endpoint">CV WebSocket</label>
          <input id="endpoint" value={draft.endpoint} onChange={(e) => set("endpoint", e.target.value)} className={`${field} mt-1.5 w-full font-mono`} />
          <p className="mt-1 text-[10.5px] text-muted-foreground">Read-only sensor events are relayed by the background worker. CV connectivity is off by default in the extension config.</p>
          {!draft.demoMode && <p className="mt-1 text-[10.5px] text-muted-foreground">Live mode currently reports CV events only; agent selection, pause, and voice controls are not connected.</p>}
          {!validWs && <p className="mt-1 text-[10.5px] text-destructive">Must start with ws:// or wss://</p>}
        </div>
        <Row label="Automatic selection" hint="Let the agent pick the most reliable input"><Switch checked={draft.autoSelect} onCheckedChange={(v) => set("autoSelect", v)} /></Row>
        <Row label="Preferred modality" hint="Wins ties within 5% reliability">
          <select value={draft.preferred} onChange={(e) => set("preferred", e.target.value as ModalityId)} className={field}>
            {MODALITY_IDS.map((id) => <option key={id} value={id}>{MODALITY_LABEL[id]}</option>)}
          </select>
        </Row>
        <Row label="Allow manual override"><Switch checked={draft.allowManualOverride} onCheckedChange={(v) => set("allowManualOverride", v)} /></Row>
        <div className="py-2.5">
          <div className="flex justify-between text-[12.5px]"><span>Gesture sensitivity</span><span className="font-mono text-muted-foreground">{draft.gestureSensitivity}</span></div>
          <Slider className="mt-2.5" value={[draft.gestureSensitivity]} min={0} max={100} step={5} onValueChange={([v]) => set("gestureSensitivity", v ?? 0)} />
        </div>
        <div className="py-2.5">
          <div className="flex justify-between text-[12.5px]"><span>Command cooldown</span><span className="font-mono text-muted-foreground">{draft.cooldownMs} ms</span></div>
          <Slider className="mt-2.5" value={[draft.cooldownMs]} min={100} max={2000} step={50} onValueChange={([v]) => set("cooldownMs", v ?? 0)} />
        </div>
        <Row label="Voice confirmation" hint="Ambiguous commands always require confirmation">
          <select value={draft.voiceConfirm} onChange={(e) => set("voiceConfirm", e.target.value as Settings["voiceConfirm"])} className={field}>
            <option value="ambiguous">Ambiguous only</option>
            <option value="all">All commands</option>
          </select>
        </Row>
        <Row label="Notifications" hint="Notify on modality switches"><Switch checked={draft.notifications} onCheckedChange={(v) => set("notifications", v)} /></Row>
        <Row label="Demo mode" hint="Isolated simulation, no real actions"><Switch checked={draft.demoMode} onCheckedChange={(v) => set("demoMode", v)} /></Row>
      </div>

      <div className="mt-3 flex gap-2">
        <button onClick={() => setDraft(state.settings)} disabled={!dirty} className="flex-1 rounded-md border border-border bg-surface-raised py-1.5 text-[12px] disabled:opacity-40">Discard</button>
        <button onClick={save} disabled={!dirty} className="flex-1 rounded-md bg-primary py-1.5 text-[12px] font-medium text-primary-foreground disabled:opacity-40">Save changes</button>
      </div>
    </div>
  );
}
