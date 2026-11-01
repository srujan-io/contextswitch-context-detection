import { Cpu, Hand, Mic, ScanFace, type LucideIcon } from "lucide-react";
import type { ModalityId, ModalityStatus } from "@/types/contextSwitch";

export const MODALITY_LABEL: Record<ModalityId, string> = {
  voice: "Voice",
  head: "Head Tracking",
  hand: "Hand Gestures",
  imu: "IMU Motion",
};
export const MODALITY_SHORT: Record<ModalityId, string> = { voice: "VOICE", head: "HEAD", hand: "HAND", imu: "IMU" };
export const MODALITY_ICON: Record<ModalityId, LucideIcon> = { voice: Mic, head: ScanFace, hand: Hand, imu: Cpu };
export const MODALITY_METRIC_LABEL: Record<ModalityId, string> = {
  voice: "Speech confidence",
  head: "Face tracking",
  hand: "Gesture confidence",
  imu: "Signal quality",
};

export const STATUS_LABEL: Record<ModalityStatus, string> = {
  active: "Active",
  available: "Available",
  listening: "Listening",
  unavailable: "Unavailable",
  tracking_lost: "Tracking Lost",
  not_detected: "Not Detected",
  connected: "Connected",
  calibrating: "Calibrating",
  disconnected: "Disconnected",
};

export type Tone = "active" | "ok" | "warn" | "off";
export function statusTone(s: ModalityStatus): Tone {
  if (s === "active" || s === "listening") return "active";
  if (s === "available" || s === "connected") return "ok";
  if (s === "calibrating") return "warn";
  return "off";
}

export const fmtTime = (ts: number) =>
  new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);
