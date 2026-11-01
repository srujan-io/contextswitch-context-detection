import { useState } from "react";
import { LiveConsole } from '@/components/LiveConsole';
import { createFileRoute } from "@tanstack/react-router";
import { ContextSwitchProvider } from "@/hooks/useContextSwitchState";
import { Header } from "@/components/Header";
import { ActiveModalityCard } from "@/components/ActiveModalityCard";
import { ModalityStatusGrid } from "@/components/ModalityStatusGrid";
import { AgentIntelligence } from "@/components/AgentIntelligence";
import { CommandActivity } from "@/components/CommandActivity";
import { VoicePanel } from "@/components/VoicePanel";
import { ReliabilityMonitor } from "@/components/ReliabilityMonitor";
import { DemoControls } from "@/components/DemoControls";
import { SettingsPanel } from "@/components/SettingsPanel";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Monitoring Dashboard — ContextSwitch" },
      { name: "description", content: "Detailed live monitoring of modality reliability, agent decisions and command activity." },
      { property: "og:title", content: "Monitoring Dashboard — ContextSwitch" },
      { property: "og:description", content: "Live modality reliability, agent reasoning and command activity for ContextSwitch." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LiveConsole,
});

function Dashboard() {
  const [settings, setSettings] = useState(false);
  return (
    <ContextSwitchProvider>
      <main className="min-h-screen bg-hero">
        <div className="mx-auto max-w-6xl px-5 py-5">
          <Header variant="dashboard" onSettings={() => setSettings((s) => !s)} />
          <div className="mt-5 grid gap-3 lg:grid-cols-[1.15fr_1fr_1fr]">
            <div className="space-y-3">
              <ActiveModalityCard />
              <ModalityStatusGrid />
              <DemoControls onEnable={() => setSettings(true)} />
            </div>
            <div className="space-y-3">
              <AgentIntelligence timelineLimit={12} />
              <VoicePanel />
            </div>
            <div className="space-y-3">
              {settings ? (
                <div className="h-[640px]"><SettingsPanel onBack={() => setSettings(false)} /></div>
              ) : (
                <>
                  <ReliabilityMonitor defaultOpen />
                  <CommandActivity limit={10} />
                </>
              )}
            </div>
          </div>
        </div>
      </main>
    </ContextSwitchProvider>
  );
}
