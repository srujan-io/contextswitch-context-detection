import { describe, it, expect } from "vitest";
import { pickModality, canSelectManually } from "./agent";
import type { ModalityState } from "@/types/contextSwitch";

const m = (id: ModalityState["id"], confidence: number | null, available = true): ModalityState => ({
  id, confidence, available, status: available ? "available" : "unavailable",
});

describe("agent selection", () => {
  it("picks the most reliable available modality", () => {
    expect(pickModality([m("voice", 0.4), m("head", 0.9), m("hand", 0.7)], "voice")).toBe("head");
  });
  it("ignores modalities below the 0.6 threshold", () => {
    expect(pickModality([m("voice", 0.59), m("head", 0.5)], "voice")).toBeNull();
  });
  it("ignores unavailable modalities even with high confidence", () => {
    expect(pickModality([m("voice", 0.99, false), m("imu", 0.7)], "voice")).toBe("imu");
  });
  it("prefers the preferred modality within the 5% margin", () => {
    expect(pickModality([m("voice", 0.86), m("head", 0.9)], "voice")).toBe("voice");
    expect(pickModality([m("voice", 0.8), m("head", 0.9)], "voice")).toBe("head");
  });
  it("blocks manual selection of unavailable modalities", () => {
    expect(canSelectManually([m("voice", 0.9, false)], "voice")).toBe(false);
    expect(canSelectManually([m("hand", 0.7)], "hand")).toBe(true);
  });
});
