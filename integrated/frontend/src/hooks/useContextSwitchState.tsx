import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from "react";
import { createBridge, type ContextSwitchBridge } from "@/services/contextSwitchBridge";
import { SimulationEngine } from "@/services/simulationEngine";
import { createSettingsStorage, DEFAULT_SETTINGS, type SettingsStorage } from "@/services/settingsStorage";
import { canSelectManually } from "@/lib/agent";
import {
  MODALITY_IDS,
  type AgentState,
  type CommandEntry,
  type ConnectionStatus,
  type CSControl,
  type CSEvent,
  type DecisionEntry,
  type DemoScenario,
  type Metric,
  type MetricKey,
  type ModalityId,
  type ModalityState,
  type SelectionMode,
  type Settings,
  type VoiceState,
} from "@/types/contextSwitch";

export interface CSState {
  ready: boolean;
  source: "simulation" | "backend";
  connection: ConnectionStatus;
  paused: boolean;
  mode: SelectionMode;
  modalities: ModalityState[];
  agent: AgentState;
  decisions: DecisionEntry[];
  commands: CommandEntry[];
  voice: VoiceState;
  metrics: Record<MetricKey, Metric>;
  scenario: DemoScenario | null;
  settings: Settings;
  lastEventAt: number | null;
}

const emptyMetric: Metric = { value: null, source: "unavailable", history: [] };
const initial = (settings: Settings = DEFAULT_SETTINGS, ready = false): CSState => ({
  ready,
  source: settings.demoMode ? "simulation" : "backend",
  connection: "disconnected",
  paused: false,
  mode: settings.autoSelect ? "auto" : "manual",
  modalities: [],
  agent: { active: null, selectedBy: "agent", reason: "", lastSwitch: null, reliability: null },
  decisions: [],
  commands: [],
  voice: { mic: "unavailable", phase: "idle", confidence: null },
  metrics: { ambientNoise: emptyMetric, face: emptyMetric, hand: emptyMetric, imu: emptyMetric, voice: emptyMetric, latency: emptyMetric },
  scenario: settings.demoMode ? "normal" : null,
  settings,
  lastEventAt: null,
});

type Action =
  | { kind: "event"; event: CSEvent }
  | { kind: "reset"; settings: Settings }
  | { kind: "mode"; mode: SelectionMode }
  | { kind: "scenario"; scenario: DemoScenario }
  | { kind: "clearConfirmation" }
  | { kind: "settings"; settings: Settings };

function applyEvent(s: CSState, e: CSEvent): CSState {
  const now = Date.now();
  switch (e.type) {
    case "CONNECTION_STATUS":
      return {
        ...s, connection: e.status,
        metrics: e.latencyMs !== undefined
          ? { ...s.metrics, latency: { value: e.latencyMs, source: s.source === "simulation" ? "simulated" : "measured", history: [...s.metrics.latency.history, e.latencyMs].slice(-24) } }
          : s.metrics,
      };
    case "MODALITY_STATUS": {
      const voice = e.modalities.find((m) => m.id === "voice");
      return {
        ...s, modalities: e.modalities,
        voice: voice ? { ...s.voice, mic: voice.available ? "available" : "unavailable", phase: !voice.available ? "idle" : s.agent.active === "voice" ? (s.voice.phase === "idle" ? "listening" : s.voice.phase) : "idle" } : s.voice,
      };
    }
    case "ACTIVE_MODALITY_CHANGED":
      return { ...s, agent: { ...s.agent, active: e.modality, selectedBy: e.selectedBy, reason: e.reason, lastSwitch: e.ts } };
    case "AGENT_DECISION":
      return { ...s, decisions: [e.entry, ...s.decisions].slice(0, 30), agent: { ...s.agent, reliability: e.reliability ?? s.agent.reliability } };
    case "COMMAND_RECEIVED":
      return { ...s, lastEventAt: now, commands: [e.command, ...s.commands.filter((c) => c.id !== e.command.id)].slice(0, 10) };
    case "SENSOR_ACTION": {
      const previous = new Map(s.modalities.map((modality) => [modality.id, modality] as const));
      const trackingLost = e.action === "TRACKING_LOST";
      previous.set(e.source, {
        id: e.source,
        status: trackingLost ? (e.source === "head" ? "tracking_lost" : "not_detected") : "active",
        available: !trackingLost,
        confidence: null,
      });
      const modalities = MODALITY_IDS.map((id) =>
        previous.get(id) ?? { id, status: "unavailable" as const, available: false, confidence: null },
      );
      const target = Object.keys(e.parameters).length > 0 ? JSON.stringify(e.parameters) : undefined;
      const command: CommandEntry = {
        id: e.id,
        source: e.source,
        action: e.action,
        target,
        ts: e.ts,
        status: "detected",
      };
      return {
        ...s,
        modalities,
        lastEventAt: now,
        commands: [command, ...s.commands.filter((c) => c.id !== command.id)].slice(0, 10),
      };
    }
    case "COMMAND_RESULT":
      return { ...s, lastEventAt: now, commands: s.commands.map((c) => (c.id === e.id ? { ...c, status: e.status } : c)) };
    case "VOICE_TRANSCRIPT":
      return { ...s, voice: { ...s.voice, transcript: e.transcript, intent: e.intent, confidence: e.confidence, phase: e.phase ?? s.voice.phase, mic: e.mic ?? s.voice.mic } };
    case "VOICE_CONFIRMATION_REQUIRED":
      return { ...s, voice: { ...s.voice, phase: "processing", pendingConfirmation: e.confirmation } };
    case "METRICS": {
      const metrics = { ...s.metrics };
      for (const [k, m] of Object.entries(e.metrics) as [MetricKey, { value: number | null; source: Metric["source"] }][]) {
        metrics[k] = { value: m.value, source: m.source, history: m.value === null ? metrics[k].history : [...metrics[k].history, m.value].slice(-24) };
      }
      return { ...s, metrics };
    }
    case "SYSTEM_PAUSED":
      return { ...s, paused: true };
    case "SYSTEM_RESUMED":
      return { ...s, paused: false };
  }
}

function reducer(s: CSState, a: Action): CSState {
  switch (a.kind) {
    case "event": return applyEvent(s, a.event);
    case "reset": return initial(a.settings, true);
    case "mode": return { ...s, mode: a.mode };
    case "scenario": return { ...s, scenario: a.scenario };
    case "clearConfirmation": return { ...s, voice: { ...s.voice, pendingConfirmation: undefined, phase: "listening" } };
    case "settings": return { ...s, settings: a.settings };
  }
}

export interface CSApi {
  state: CSState;
  storageKind: SettingsStorage["kind"];
  bridgeKind: ContextSwitchBridge["kind"];
  togglePause(): void;
  setMode(mode: SelectionMode): void;
  selectModality(id: ModalityId): boolean;
  confirmVoice(accept: boolean): void;
  runScenario(s: DemoScenario): void;
  saveSettings(s: Settings): Promise<void>;
}

const Ctx = createContext<CSApi | null>(null);

export function ContextSwitchProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, () => initial());
  const storage = useMemo(() => (typeof window === "undefined" ? null : createSettingsStorage()), []);
  const bridge = useMemo(() => (typeof window === "undefined" ? null : createBridge()), []);
  const sim = useRef<SimulationEngine | null>(null);

  // Load persisted settings once.
  useEffect(() => {
    storage?.load().then((s) => dispatch({ kind: "reset", settings: s }));
  }, [storage]);

  // Subscribe to exactly one event source: the isolated simulation OR the background bridge.
  const demo = state.settings.demoMode;
  useEffect(() => {
    if (!state.ready || !bridge) return;
    const onEvent = (event: CSEvent) => dispatch({ kind: "event", event });
    if (demo) {
      const engine = new SimulationEngine(onEvent);
      sim.current = engine;
      engine.start(state.settings.preferred, state.mode);
      return () => { engine.stop(); sim.current = null; };
    }
    return bridge.subscribe(onEvent);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.ready, demo, bridge]);

  const send = useCallback((c: CSControl) => {
    if (sim.current) { sim.current.handle(c); return true; }
    return bridge?.send(c) ?? false;
  }, [bridge]);

  const api: CSApi = {
    state,
    storageKind: storage?.kind ?? "local-mock",
    bridgeKind: bridge?.kind ?? "unavailable",
    togglePause() {
      if (state.source === "backend") return;
      const sent = send({ type: state.paused ? "RESUME" : "PAUSE" });
      // Without a backend, still reflect the user's intent locally.
      if (!sent) dispatch({ kind: "event", event: { type: state.paused ? "SYSTEM_RESUMED" : "SYSTEM_PAUSED" } });
    },
    setMode(mode) {
      if (state.source === "backend") return;
      dispatch({ kind: "mode", mode });
      send({ type: "SET_MODE", mode });
    },
    selectModality(id) {
      if (state.source === "backend" || state.mode !== "manual" || !canSelectManually(state.modalities, id)) return false;
      return send({ type: "SELECT_MODALITY", modality: id });
    },
    confirmVoice(accept) {
      if (state.source === "backend") return;
      const p = state.voice.pendingConfirmation;
      if (!p) return;
      send({ type: "VOICE_CONFIRMATION", id: p.id, accept });
      dispatch({ kind: "clearConfirmation" });
    },
    runScenario(scenario) {
      if (!sim.current) return;
      dispatch({ kind: "scenario", scenario });
      sim.current.handle({ type: "RUN_SCENARIO", scenario });
    },
    async saveSettings(s) {
      await storage?.save(s);
      const demoChanged = s.demoMode !== state.settings.demoMode;
      if (demoChanged) dispatch({ kind: "reset", settings: s });
      else {
        dispatch({ kind: "settings", settings: s });
        send({ type: "UPDATE_SETTINGS", settings: s });
        const mode = s.autoSelect ? "auto" : "manual";
        if (mode !== state.mode) api.setMode(mode);
      }
    },
  };

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useContextSwitchState(): CSApi {
  const v = useContext(Ctx);
  if (!v) throw new Error("useContextSwitchState must be used inside ContextSwitchProvider");
  return v;
}
