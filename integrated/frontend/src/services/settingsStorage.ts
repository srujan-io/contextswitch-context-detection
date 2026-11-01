import type { Settings } from "@/types/contextSwitch";

export const DEFAULT_SETTINGS: Settings = {
  endpoint: "ws://127.0.0.1:8000/ws/cv",
  autoSelect: true,
  preferred: "voice",
  allowManualOverride: true,
  gestureSensitivity: 60,
  cooldownMs: 600,
  voiceConfirm: "ambiguous",
  notifications: true,
  demoMode: false,
};

const KEY = "contextswitch.settings";

export interface SettingsStorage {
  kind: "chrome.storage" | "local-mock";
  load(): Promise<Settings>;
  save(s: Settings): Promise<void>;
}

type ChromeStorage = {
  storage?: { local?: { get(k: string): Promise<Record<string, unknown>>; set(v: Record<string, unknown>): Promise<void> } };
};

export function createSettingsStorage(): SettingsStorage {
  const chromeLocal = (globalThis as unknown as { chrome?: ChromeStorage }).chrome?.storage?.local;
  if (chromeLocal) {
    return {
      kind: "chrome.storage",
      async load() {
        const r = await chromeLocal.get(KEY);
        return { ...DEFAULT_SETTINGS, ...((r[KEY] as Partial<Settings>) ?? {}) };
      },
      save: (s) => chromeLocal.set({ [KEY]: s }),
    };
  }
  // Isolated mock adapter for the standalone preview.
  return {
    kind: "local-mock",
    async load() {
      try {
        return { ...DEFAULT_SETTINGS, ...JSON.parse(localStorage.getItem(KEY) ?? "{}") };
      } catch {
        return DEFAULT_SETTINGS;
      }
    },
    async save(s) {
      localStorage.setItem(KEY, JSON.stringify(s));
    },
  };
}
