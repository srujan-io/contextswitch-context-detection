import { describe, expect, it } from "vitest";
import { defaultAdapter } from "./contextSwitchBridge";

describe("CV event adapter", () => {
  it("maps discrete HEAD and HAND events without claiming they were executed", () => {
    expect(
      defaultAdapter.toEvent({
        source: "HEAD",
        action: "HEAD_UP",
        parameters: { pitch: 5 },
        timestamp: 123,
      }),
    ).toEqual({
      type: "SENSOR_ACTION",
      id: expect.stringMatching(/^cv-head-123-HEAD_UP-\d+$/),
      source: "head",
      action: "HEAD_UP",
      parameters: { pitch: 5 },
      ts: 123,
    });
  });

  it("ignores high-frequency cursor events and unknown sensor sources", () => {
    expect(defaultAdapter.toEvent({ source: "HAND", action: "CURSOR_MOVE" })).toBeNull();
    expect(defaultAdapter.toEvent({ source: "VOICE", action: "TRANSCRIBE" })).toBeNull();
  });
});
