import { useState } from "react";
import { LiveConsole } from './LiveConsole';
import { ExtensionConsent } from './ExtensionConsent';
import { Header } from "./Header";
import { ActiveModalityCard } from "./ActiveModalityCard";
import { ModalityStrip } from "./ModalityStrip";
import { AgentIntelligence } from "./AgentIntelligence";
import { CommandActivity } from "./CommandActivity";
import { VoicePanel } from "./VoicePanel";
import { ReliabilityMonitor } from "./ReliabilityMonitor";
import { DemoControls } from "./DemoControls";
import { SettingsPanel } from "./SettingsPanel";
import { useContextSwitchState } from "@/hooks/useContextSwitchState";
import { cn } from "@/lib/utils";

const TABS = [
  { id: "activity", label: "Activity" },
  { id: "agent", label: "Decisions" },
  { id: "sensors", label: "Sensors" },
] as const;
type Tab = (typeof TABS)[number]["id"];

/** The Chrome extension popup surface (400×600). Bundle this for the MV3 action popup. */
export function PopupView() { return <ExtensionConsent><LiveConsole surface="popup" /></ExtensionConsent>; }
export function SimulationPopupView() {
  const [view, setView] = useState<"main" | "settings">("main");
  const [tab, setTab] = useState<Tab>("activity");
  const { state } = useContextSwitchState();
  const needsConfirm = !!state.voice.pendingConfirmation;

  if (view === "settings") {
    return <div className="h-[600px] w-[400px] bg-background p-3.5"><SettingsPanel onBack={() => setView("main")} /></div>;
  }

  return (
    <div className="flex h-[600px] w-[400px] flex-col overflow-hidden bg-background">
      <div className="px-3.5 pb-2.5 pt-3"><Header variant="popup" onSettings={() => setView("settings")} /></div>

      <div className="space-y-2 px-3.5">
        <ActiveModalityCard />
        <ModalityStrip />
        {needsConfirm && <VoicePanel />}
      </div>

      <nav className="mt-3 flex gap-4 border-b border-border px-3.5 text-[12px]" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cn("-mb-px border-b-2 pb-2 transition-colors duration-150", tab === t.id ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground")}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="flex-1 space-y-2 overflow-y-auto p-3.5">
        {tab === "activity" && (<><CommandActivity limit={8} />{!needsConfirm && <VoicePanel />}</>)}
        {tab === "agent" && <AgentIntelligence timelineLimit={8} />}
        {tab === "sensors" && <ReliabilityMonitor defaultOpen />}
      </div>

      <div className="border-t border-border px-3.5 py-2.5"><DemoControls compact onEnable={() => setView("settings")} /></div>
    </div>
  );
}
