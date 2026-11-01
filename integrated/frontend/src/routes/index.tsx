import { createFileRoute } from "@tanstack/react-router";
import { ContextSwitchProvider } from "@/hooks/useContextSwitchState";
import { PopupView } from "@/components/PopupView";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "ContextSwitch — Adaptive Interaction Engine" },
      { name: "description", content: "Hands-free control for technical software. ContextSwitch picks voice, head, hand or IMU input automatically." },
      { property: "og:title", content: "ContextSwitch — Adaptive Interaction Engine" },
      { property: "og:description", content: "An AI agent that switches between voice, head tracking, hand gestures and IMU input to keep engineers in control." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <ContextSwitchProvider>
      <main className="flex min-h-screen items-center justify-center bg-hero p-6">
        <div className="overflow-hidden rounded-xl shadow-panel">
          <PopupView />
        </div>
      </main>
    </ContextSwitchProvider>
  );
}
