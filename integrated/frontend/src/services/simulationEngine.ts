/**
 * Demo-mode simulation. Fully isolated: it never talks to the bridge/backend and
 * never dispatches real KiCanvas actions. Every value it emits is tagged "simulated".
 */
import { canSelectManually, pickModality } from "@/lib/agent";
import type {
  CSControl, CSEvent, DemoScenario, ModalityId, ModalityState, SelectionMode,
} from "@/types/contextSwitch";
import { MODALITY_LABEL } from "@/lib/modalities";

type Base = { available: boolean; confidence: number | null; lostStatus: ModalityState["status"] };

const SCENARIOS: Record<DemoScenario, { bases: Record<ModalityId, Base>; noise: number; note: string }> = {
  normal: {
    noise: 0.28,
    note: "Normal conditions restored across all sensors.",
    bases: {
      voice: { available: true, confidence: 0.91, lostStatus: "unavailable" },
      head: { available: true, confidence: 0.88, lostStatus: "tracking_lost" },
      hand: { available: true, confidence: 0.74, lostStatus: "not_detected" },
      imu: { available: true, confidence: 0.82, lostStatus: "disconnected" },
    },
  },
  noise: {
    noise: 0.82,
    note: "Ambient noise increased to ~78 dB.",
    bases: {
      voice: { available: true, confidence: 0.41, lostStatus: "unavailable" },
      head: { available: true, confidence: 0.9, lostStatus: "tracking_lost" },
      hand: { available: true, confidence: 0.76, lostStatus: "not_detected" },
      imu: { available: true, confidence: 0.83, lostStatus: "disconnected" },
    },
  },
  camera: {
    noise: 0.3,
    note: "Camera obstructed — face and hand tracking lost.",
    bases: {
      voice: { available: true, confidence: 0.9, lostStatus: "unavailable" },
      head: { available: false, confidence: null, lostStatus: "tracking_lost" },
      hand: { available: false, confidence: null, lostStatus: "not_detected" },
      imu: { available: true, confidence: 0.8, lostStatus: "disconnected" },
    },
  },
  mic: {
    noise: 0.3,
    note: "Microphone became unavailable.",
    bases: {
      voice: { available: false, confidence: null, lostStatus: "unavailable" },
      head: { available: true, confidence: 0.89, lostStatus: "tracking_lost" },
      hand: { available: true, confidence: 0.73, lostStatus: "not_detected" },
      imu: { available: true, confidence: 0.81, lostStatus: "disconnected" },
    },
  },
  recovery: {
    noise: 0.25,
    note: "Sensors recovered. IMU recalibrated.",
    bases: {
      voice: { available: true, confidence: 0.93, lostStatus: "unavailable" },
      head: { available: true, confidence: 0.9, lostStatus: "tracking_lost" },
      hand: { available: true, confidence: 0.78, lostStatus: "not_detected" },
      imu: { available: true, confidence: 0.86, lostStatus: "disconnected" },
    },
  },
};

const ACTIONS: Record<ModalityId, Array<[string, string?]>> = {
  voice: [["LOCATE_COMPONENT", "J106"], ["LOCATE_COMPONENT", "U3"], ["ZOOM_FIT"], ["HIGHLIGHT_NET", "VBUS"]],
  head: [["SCROLL_DOWN"], ["SCROLL_UP"], ["ZOOM_IN"], ["ZOOM_OUT"], ["PAN_LEFT"]],
  hand: [["NEXT_PAGE"], ["PREV_PAGE"], ["ZOOM_IN"], ["SELECT"]],
  imu: [["PAN_RIGHT"], ["PAN_UP"], ["ROTATE_VIEW"], ["SCROLL_DOWN"]],
};
const PHRASES: Record<string, string> = {
  LOCATE_COMPONENT: "Locate",
  ZOOM_FIT: "Zoom to fit",
  HIGHLIGHT_NET: "Highlight net",
};

let seq = 0;
const uid = () => `sim-${Date.now().toString(36)}-${(seq++).toString(36)}`;
const clamp = (v: number) => Math.max(0, Math.min(1, v));
const jitter = (v: number, amt = 0.03) => clamp(v + (Math.random() - 0.5) * 2 * amt);

export class SimulationEngine {
  private scenario: DemoScenario = "normal";
  private mode: SelectionMode = "auto";
  private preferred: ModalityId = "voice";
  private active: ModalityId | null = null;
  private paused = false;
  private tickN = 0;
  private timer: ReturnType<typeof setInterval> | undefined;
  private current: ModalityState[] = [];

  constructor(private emit: (e: CSEvent) => void) {}

  start(preferred: ModalityId, mode: SelectionMode) {
    this.preferred = preferred;
    this.mode = mode;
    this.emit({ type: "CONNECTION_STATUS", status: "connected", latencyMs: 24 });
    this.refresh(true);
    this.decide("Simulation started under normal conditions.");
    this.timer = setInterval(() => this.tick(), 1600);
  }

  stop() {
    clearInterval(this.timer);
  }

  handle(c: CSControl) {
    switch (c.type) {
      case "PAUSE":
        this.paused = true;
        this.emit({ type: "SYSTEM_PAUSED" });
        this.note("observation", "Input paused by user. Commands will not be dispatched.");
        break;
      case "RESUME":
        this.paused = false;
        this.emit({ type: "SYSTEM_RESUMED" });
        this.note("observation", "Input resumed.");
        break;
      case "SET_MODE":
        this.mode = c.mode;
        if (c.mode === "auto") this.decide("Automatic selection re-enabled.");
        else this.note("override", "Manual mode — agent recommendations paused.");
        break;
      case "SELECT_MODALITY":
        if (!canSelectManually(this.current, c.modality)) {
          this.note("warning", `${MODALITY_LABEL[c.modality]} is unavailable and cannot be selected.`);
          return;
        }
        this.setActive(c.modality, "manual", `Manual override: ${MODALITY_LABEL[c.modality]} selected by user.`);
        break;
      case "RUN_SCENARIO":
        this.scenario = c.scenario;
        this.refresh(true);
        this.note("observation", SCENARIOS[c.scenario].note);
        this.decide(SCENARIOS[c.scenario].note);
        break;
      case "VOICE_CONFIRMATION": {
        const cmd = { id: c.id, source: "voice" as const, action: "OPEN_SHEET", target: "3.3V Regulator", ts: Date.now() };
        if (c.accept) {
          this.emit({ type: "COMMAND_RECEIVED", command: { ...cmd, status: "pending" } });
          setTimeout(() => this.emit({ type: "COMMAND_RESULT", id: c.id, status: "simulated" }), 700);
        } else {
          this.emit({ type: "COMMAND_RECEIVED", command: { ...cmd, status: "rejected" } });
        }
        this.emit({ type: "VOICE_TRANSCRIPT", transcript: "open the regulator sheet", intent: "OPEN_SHEET", confidence: 0.58, phase: "listening" });
        break;
      }
      case "UPDATE_SETTINGS":
        this.preferred = c.settings.preferred;
        break;
    }
  }

  private refresh(force = false) {
    const sc = SCENARIOS[this.scenario];
    this.current = (Object.keys(sc.bases) as ModalityId[]).map((id) => {
      const b = sc.bases[id];
      const isActive = this.active === id;
      const status: ModalityState["status"] = !b.available
        ? b.lostStatus
        : isActive
          ? id === "voice" ? "listening" : "active"
          : id === "imu" ? (this.scenario === "recovery" && this.tickN < 2 ? "calibrating" : "connected") : "available";
      return { id, available: b.available, status, confidence: b.confidence === null ? null : force ? b.confidence : jitter(b.confidence) };
    });
    this.emit({ type: "MODALITY_STATUS", modalities: this.current });
    const get = (id: ModalityId) => this.current.find((m) => m.id === id)?.confidence ?? null;
    this.emit({
      type: "METRICS",
      metrics: {
        ambientNoise: { value: jitter(sc.noise, 0.04), source: "simulated" },
        face: { value: get("head"), source: get("head") === null ? "unavailable" : "simulated" },
        hand: { value: get("hand"), source: get("hand") === null ? "unavailable" : "simulated" },
        imu: { value: get("imu"), source: "simulated" },
        voice: { value: get("voice"), source: get("voice") === null ? "unavailable" : "simulated" },
        latency: { value: 18 + Math.round(Math.random() * 22), source: "simulated" },
      },
    });
  }

  private decide(context: string) {
    if (this.mode === "manual" && this.active && canSelectManually(this.current, this.active)) return;
    const pick = pickModality(this.current, this.preferred);
    if (pick === this.active) {
      if (pick) this.note("stable", `${MODALITY_LABEL[pick]} remains the most reliable input.`, pick);
      return;
    }
    const prev = this.active;
    let reason: string;
    if (!pick) reason = "No modality meets the reliability threshold. Commands are held.";
    else if (prev) {
      const prevState = this.current.find((m) => m.id === prev);
      const why = !prevState?.available
        ? `${MODALITY_LABEL[prev]} became unavailable`
        : `${MODALITY_LABEL[prev]} confidence dropped below the reliability threshold`;
      reason = `${why}. Switched to ${MODALITY_LABEL[pick]} to maintain uninterrupted control.`;
    } else reason = `${MODALITY_LABEL[pick]} has the highest confidence. ${context}`;
    this.setActive(pick, "agent", reason);
  }

  private setActive(id: ModalityId | null, by: "agent" | "manual", reason: string) {
    this.active = id;
    const ts = Date.now();
    this.emit({ type: "ACTIVE_MODALITY_CHANGED", modality: id, selectedBy: by, reason, ts });
    this.note(by === "manual" ? "override" : id ? "switched" : "warning",
      id ? `${by === "manual" ? "Override →" : "Switched to"} ${MODALITY_LABEL[id]}` : "No reliable modality", id ?? undefined);
    this.refresh();
  }

  private note(kind: Parameters<typeof this.mkEntry>[0], message: string, modality?: ModalityId) {
    const reliability = this.active ? this.current.find((m) => m.id === this.active)?.confidence ?? undefined : undefined;
    this.emit({ type: "AGENT_DECISION", entry: this.mkEntry(kind, message, modality), reliability });
  }

  private mkEntry(kind: "selected" | "switched" | "observation" | "override" | "stable" | "warning", message: string, modality?: ModalityId) {
    return { id: uid(), ts: Date.now(), kind, message, modality };
  }

  private tick() {
    this.tickN++;
    this.refresh();
    if (this.paused || !this.active) return;
    const src = this.active;
    if (src === "voice" && this.tickN % 7 === 0) {
      this.emit({ type: "VOICE_TRANSCRIPT", transcript: "open the regulator sheet", intent: "OPEN_SHEET?", confidence: 0.58, phase: "processing" });
      this.emit({ type: "VOICE_CONFIRMATION_REQUIRED", confirmation: { id: uid(), prompt: "Did you mean open the 3.3V Regulator sheet?", intent: "OPEN_SHEET", target: "3.3V Regulator" } });
      return;
    }
    if (Math.random() > 0.45) return;
    const [action, target] = ACTIONS[src][Math.floor(Math.random() * ACTIONS[src].length)]!;
    const id = uid();
    if (src === "voice") {
      this.emit({ type: "VOICE_TRANSCRIPT", transcript: `${PHRASES[action] ?? action}${target ? " " + target : ""}`, intent: action, confidence: jitter(0.9, 0.05), phase: "listening" });
    }
    this.emit({ type: "COMMAND_RECEIVED", command: { id, source: src, action, target, ts: Date.now(), status: "pending" } });
    setTimeout(() => this.emit({ type: "COMMAND_RESULT", id, status: Math.random() < 0.06 ? "failed" : "simulated" }), 350 + Math.random() * 500);
  }
}
