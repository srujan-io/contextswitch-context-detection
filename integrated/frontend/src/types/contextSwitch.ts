/**
 * ContextSwitch frontend contract.
 * Frontend event contract. The live bridge currently provides CV connection and sensor events;
 * other backend event types remain available for future integrations.
 */

export type ModalityId = "voice" | "head" | "hand" | "imu";
export const MODALITY_IDS: ModalityId[] = ["voice", "head", "hand", "imu"];

export type ModalityStatus =
  | "active"
  | "available"
  | "listening"
  | "unavailable"
  | "tracking_lost"
  | "not_detected"
  | "connected"
  | "calibrating"
  | "disconnected";

export interface ModalityState {
  id: ModalityId;
  status: ModalityStatus;
  /** Whether the agent may select this modality. */
  available: boolean;
  /** 0..1, or null when unknown. */
  confidence: number | null;
}

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";
export type SelectionMode = "auto" | "manual";
export type DataSource = "measured" | "simulated" | "unavailable";

/** "simulated" is used in demo mode — never shown as "executed". */
export type CommandStatus = "detected" | "pending" | "executed" | "failed" | "rejected" | "simulated";

export interface CommandEntry {
  id: string;
  source: ModalityId;
  action: string;
  target?: string | undefined;
  ts: number;
  status: CommandStatus;
}

export type DecisionKind = "selected" | "switched" | "observation" | "override" | "stable" | "warning";

export interface DecisionEntry {
  id: string;
  ts: number;
  kind: DecisionKind;
  message: string;
  modality?: ModalityId | undefined;
}

export interface VoiceConfirmation {
  id: string;
  prompt: string;
  intent: string;
  target?: string | undefined;
}

export interface VoiceState {
  mic: "available" | "unavailable";
  phase: "idle" | "listening" | "processing";
  transcript?: string | undefined;
  intent?: string | undefined;
  confidence: number | null;
  pendingConfirmation?: VoiceConfirmation | undefined;
}

export interface Metric {
  value: number | null;
  source: DataSource;
  history: number[];
}

export type MetricKey = "ambientNoise" | "face" | "hand" | "imu" | "voice" | "latency";

export interface AgentState {
  active: ModalityId | null;
  selectedBy: "agent" | "manual";
  reason: string;
  lastSwitch: number | null;
  reliability: number | null;
}

export interface Settings {
  endpoint: string;
  autoSelect: boolean;
  preferred: ModalityId;
  allowManualOverride: boolean;
  gestureSensitivity: number;
  cooldownMs: number;
  voiceConfirm: "ambiguous" | "all";
  notifications: boolean;
  demoMode: boolean;
}

export type DemoScenario = "normal" | "noise" | "camera" | "mic" | "recovery";

/* ---------- Events (inbound: backend/simulation → UI) ---------- */

export type CSEvent =
  | { type: "CONNECTION_STATUS"; status: ConnectionStatus; latencyMs?: number | undefined }
  | { type: "MODALITY_STATUS"; modalities: ModalityState[] }
  | { type: "ACTIVE_MODALITY_CHANGED"; modality: ModalityId | null; selectedBy: "agent" | "manual"; reason: string; ts: number }
  | { type: "AGENT_DECISION"; entry: DecisionEntry; reliability?: number | undefined }
  | { type: "COMMAND_RECEIVED"; command: CommandEntry }
  | { type: "SENSOR_ACTION"; id: string; source: "head" | "hand"; action: string; parameters: Record<string, unknown>; ts: number }
  | { type: "COMMAND_RESULT"; id: string; status: CommandStatus }
  | { type: "VOICE_TRANSCRIPT"; transcript: string; intent?: string; confidence: number | null; phase?: VoiceState["phase"]; mic?: VoiceState["mic"] }
  | { type: "VOICE_CONFIRMATION_REQUIRED"; confirmation: VoiceConfirmation }
  | { type: "METRICS"; metrics: Partial<Record<MetricKey, { value: number | null; source: DataSource }>> }
  | { type: "SYSTEM_PAUSED" }
  | { type: "SYSTEM_RESUMED" };

/* ---------- Controls (outbound: UI → background/backend) ---------- */

export type CSControl =
  | { type: "PAUSE" }
  | { type: "RESUME" }
  | { type: "SET_MODE"; mode: SelectionMode }
  | { type: "SELECT_MODALITY"; modality: ModalityId }
  | { type: "VOICE_CONFIRMATION"; id: string; accept: boolean }
  | { type: "RUN_SCENARIO"; scenario: DemoScenario }
  | { type: "UPDATE_SETTINGS"; settings: Settings };
