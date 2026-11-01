/**
 * Bridge between the popup UI and the extension background service worker.
 *
 * The BACKGROUND service worker owns the optional CV WebSocket connection.
 * The popup never opens its own long-running socket — it connects a chrome.runtime Port
 * named "contextswitch-ui" and receives sensor events through it.
 *
 * The worker may forward UI settings through this port; the CV socket is read-only.
 * Keep the existing KiCanvas action polling in background.js independent.
 *   chrome.runtime.onConnect.addListener((port) => {
 *     if (port.name !== "contextswitch-ui") return;
 *     uiPorts.add(port);
 *     port.onDisconnect.addListener(() => uiPorts.delete(port));
 *   });
 */
import type { CSControl, CSEvent } from "@/types/contextSwitch";

export interface EventAdapter {
  /** Convert a raw backend message to a frontend event (return null to ignore). */
  toEvent(raw: unknown): CSEvent | null;
  /** Convert a frontend control to the backend's wire format. */
  fromControl(control: CSControl): unknown;
}

/** Map backend message types onto frontend events when their wire contracts are available. */
export const EVENT_TYPE_MAP: Record<string, CSEvent["type"]> = {
  CONNECTION_STATUS: "CONNECTION_STATUS",
  MODALITY_STATUS: "MODALITY_STATUS",
  ACTIVE_MODALITY_CHANGED: "ACTIVE_MODALITY_CHANGED",
  AGENT_DECISION: "AGENT_DECISION",
  COMMAND_RECEIVED: "COMMAND_RECEIVED",
  COMMAND_RESULT: "COMMAND_RESULT",
  VOICE_TRANSCRIPT: "VOICE_TRANSCRIPT",
  VOICE_CONFIRMATION_REQUIRED: "VOICE_CONFIRMATION_REQUIRED",
  METRICS: "METRICS",
  SYSTEM_PAUSED: "SYSTEM_PAUSED",
  SYSTEM_RESUMED: "SYSTEM_RESUMED",
};

let cvEventSequence = 0;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export const defaultAdapter: EventAdapter = {
  toEvent(raw) {
    if (!isRecord(raw)) return null;
    const message = raw;
    if (
      (message["source"] === "HEAD" || message["source"] === "HAND") &&
      typeof message["action"] === "string" &&
      message["action"] !== "CURSOR_MOVE"
    ) {
      const source = message["source"] === "HEAD" ? "head" : "hand";
      const ts = typeof message["timestamp"] === "number" && Number.isFinite(message["timestamp"])
        ? message["timestamp"]
        : Date.now();
      const parameters = isRecord(message["parameters"]) ? message["parameters"] : {};
      return {
        type: "SENSOR_ACTION",
        id: `cv-${source}-${ts}-${message["action"]}-${++cvEventSequence}`,
        source,
        action: message["action"],
        parameters,
        ts,
      };
    }
    if (!("type" in message)) return null;
    const mapped = EVENT_TYPE_MAP[String(message["type"])];
    return mapped ? ({ ...message, type: mapped } as CSEvent) : null;
  },
  fromControl: (c) => c,
};

export interface ContextSwitchBridge {
  kind: "chrome" | "unavailable";
  subscribe(onEvent: (e: CSEvent) => void): () => void;
  send(control: CSControl): boolean;
}

type ChromePort = {
  postMessage(msg: unknown): void;
  disconnect(): void;
  onMessage: { addListener(fn: (msg: unknown) => void): void };
  onDisconnect: { addListener(fn: () => void): void };
};
type ChromeLike = { runtime?: { id?: string; connect?: (o: { name: string }) => ChromePort } };

function getChrome(): ChromeLike | undefined {
  return (globalThis as unknown as { chrome?: ChromeLike }).chrome;
}

function createChromeBridge(adapter: EventAdapter): ContextSwitchBridge {
  let port: ChromePort | null = null;
  return {
    kind: "chrome",
    subscribe(onEvent) {
      let closed = false;
      let retry: ReturnType<typeof setTimeout> | undefined;
      const open = () => {
        port = getChrome()!.runtime!.connect!({ name: "contextswitch-ui" });
        port.onMessage.addListener((raw) => {
          const e = adapter.toEvent(raw);
          if (e) onEvent(e);
        });
        port.onDisconnect.addListener(() => {
          port = null;
          if (closed) return;
          onEvent({ type: "CONNECTION_STATUS", status: "reconnecting" });
          retry = setTimeout(open, 1500);
        });
      };
      open();
      return () => {
        closed = true;
        clearTimeout(retry);
        port?.disconnect();
      };
    },
    send(control) {
      if (!port) return false;
      port.postMessage(adapter.fromControl(control));
      return true;
    },
  };
}

/** Used in the standalone web preview: no background worker, so honestly report disconnected. */
function createUnavailableBridge(): ContextSwitchBridge {
  return {
    kind: "unavailable",
    subscribe(onEvent) {
      onEvent({ type: "CONNECTION_STATUS", status: "disconnected" });
      return () => {};
    },
    send: () => false,
  };
}

export function createBridge(adapter: EventAdapter = defaultAdapter): ContextSwitchBridge {
  const c = getChrome();
  return c?.runtime?.id && c.runtime.connect ? createChromeBridge(adapter) : createUnavailableBridge();
}
