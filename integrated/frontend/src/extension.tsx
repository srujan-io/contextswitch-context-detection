import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@/extensionDiagnostics";
import { PopupView } from "@/components/PopupView";
import { ContextSwitchProvider } from "@/hooks/useContextSwitchState";
import "@/styles.css";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Missing extension popup root element.");

createRoot(rootElement).render(
  <StrictMode>
      <PopupView />
  </StrictMode>,
);
