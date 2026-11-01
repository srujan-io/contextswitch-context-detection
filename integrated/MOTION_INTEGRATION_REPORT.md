# ContextSwitch motion, voice and automatic context integration

2026-11-01. Build: `contextswitch-2026.11.01.5`.

## Implemented behavior

**Hand scroll:** raise index and middle fingers, curl ring and little fingers, hold for 200 ms, then move vertically. It emits the existing HAND event envelope with `action: SCROLL` and bounded `parameters.delta_y`. The extension cancels any pending click before scrolling; scroll, pinch-click and pinch-zoom do not compete. Hand scrolling temporarily owns motion control over head gestures. Live ergonomic tuning remains a user test.

**Fast voice:** audio begins immediately without throwing away the opening words as ambient calibration. Recording ends after at least 200 ms of detected speech followed by 500 ms of silence, up to the configured recording maximum. Transcription still incurs Google Web Speech latency. Supported safe commands automatically validate and dispatch after transcription; an ACTION_READY signal wakes execution immediately instead of waiting for the next poll. Read-only KiCanvas component search no longer requires confirmation. Clarification, semantic ambiguity and any skill marked consequential still block dispatch pending approval. Typed input retains preview/execute controls. No gesture invokes Gemini per frame.

**Automatic context shift:** explicitly enabled by the 20-second calibration button. The user supplies task text, hands-occupied override and microphone selection. The camera continues to measure valid head poses and deliberate index-pointing hand poses; microphone calibration stores only RMS values, not recordings/transcripts, and sends no calibration audio externally. All gestures are suppressed during calibration. After calibration, a local threshold policy uses the last two seconds of tracking, a 70% availability threshold, 1.5-second switch dwell and 2.5× measured ambient RMS (minimum 200). Text-entry focus immediately selects TYPED. Explicit occupied hands / soldering / carrying context suppresses HAND; otherwise a deliberate control hand pose can select HAND, followed by HEAD, a recently calibrated quiet microphone/VOICE, or TYPED. VOICE selects the voice-command mode; it does not secretly start always-on recording. Manual mode selection disables automatic switching. The policy exposes its reason and actual sample counts. Hand visibility/pose is a heuristic, not an object detector or proof that a hand is free.

## Hardware discovery and exact protocol

The original teammate `contextswitch-cv/contextswitch-cv/hardware/imu_reader.py` is empty. A wider parent-folder search found the real firmware at:

`C:/Users/Srujan/Downloads/sketch_sep19b/sketch_sep19b.ino`

Its unchanged copy is in `hardware/firmware/sketch_sep19b.ino`. Its source hash was added to SOURCE_HASHES.json, bringing preservation checks to 171 originals. Earlier audit statements about missing firmware are superseded by this discovery.

- Raspberry Pi Pico H, MPU9250/6500, I2C SDA GPIO 4 / SCL GPIO 5, addresses 0x68/0x69.
- Serial 115200 baud; 50 Hz (20 ms) samples.
- Actual newline CSV: `timestamp_ms,ax,ay,az,gx,gy,gz`. Acceleration is in g; gyro is deg/s after firmware gyro-bias subtraction.
- Actual comments include `# CONTEXTSWITCH_IMU_V1`, `# CALIBRATION_START`, `# CALIBRATION_DONE`, `# STATUS,ready=1,calibrated=1,packets=...` and `# ERROR_*`.
- `s` requests status. `c` performs 300 stationary samples at 20 ms (~6 seconds).
- No magnetometer/absolute yaw is streamed. This is not an absolute 9-axis heading source.

`pico_imu.Decoder` implements exactly this protocol, including partial serial reads, invalid fields, firmware calibration/error messages and unsigned millisecond wrap. It computes pitch/roll using gravity plus gyro prediction and relative yaw from gyro. This raw-sensor complementary filter is necessary orientation estimation; it does not duplicate the existing webcam One Euro filter.

## Fusion and fallback

The serial reader and webcam are separate nonblocking input workers, but **one fused pose feeds one existing GestureRecognizer**. Six mappings, thresholds (pitch 10 / yaw 12 / roll 12), 180 ms dwell, 700 ms cooldown, neutral release ratio and head FSM remain unchanged.

Hardware time is aligned to host monotonic time with a lower-envelope receive-time offset. Duplicate/backward/jumping clocks and delayed packets invalidate calibration. Webcam capture is timestamped before processing; gyro predicts the IMU pose to that camera timestamp. Samples/frames older than 250 ms cannot drive gestures. This is software receive-time alignment, not a hardware synchronization guarantee.

Mounting is a configurable signed permutation of pitch/yaw/roll rotation axes. For the actual decoder, it is applied to raw acceleration and gyro vectors **before** orientation estimation, avoiding incorrect Euler-angle swapping with a rotated sensor. Verify the chosen basis physically; identity is only a starting configuration. General arbitrary-angle mounting is not inferred automatically.

At least 20 unique paired samples over 800 ms, with <3° spread and <5°/s stationary gyro, establish offsets and residual gyro bias. Valid sources fuse with confidence-weighted innovation and slow webcam drift anchoring. Reliability values are explicitly heuristic scores, not measured probabilities. >25° disagreement clears IMU calibration and falls back to webcam. There is no extra One Euro filter on fused output.

Disconnected/uncalibrated/unreliable IMU => webcam-only. Missing webcam => calibrated, recent IMU-only for a short confidence-decaying window (hard bound five seconds, often shorter); it then suppresses control until webcam reanchors it. Camera driver/model failures leave the serial/head loop alive. Explicit camera pause suppresses all motion. Reconnect clears host alignment/calibration, drops serial backlog and requests actual firmware status. No stale actions are queued or replayed.

## Setup and calibration

From `integrated/`:

```powershell
./.venv/Scripts/python.exe -m pip install -r requirements-hardware.txt
./.venv/Scripts/python.exe -m pip install -r requirements-imu.txt
Set-Location frontend
npm ci
npm run build
npm run build:extension
Set-Location ..
./scripts/restart.ps1
```

Reload the Chrome extension and refresh KiCanvas. Choose **Headset IMU → Serial port** from enumerated ports, supply mounting axes, then **Apply IMU connection**. Baud is the actual firmware default 115200 in the UI; API/env allow other values. No COM port is hardcoded.

Optional persistent backend `.env`:

```dotenv
CONTEXTSWITCH_IMU_PORT=<port listed by the UI or /hardware/ports>
CONTEXTSWITCH_IMU_BAUD=115200
CONTEXTSWITCH_IMU_DECODER=pico_imu:Decoder
CONTEXTSWITCH_IMU_AXES=pitch,yaw,roll
```

1. Close Arduino Serial Monitor or other serial clients. Confirm the supplied firmware is actually running; no flashing was performed by this integration.
2. Mount the sensor rigidly on the headset. Apply the connection. Wait for valid firmware status/telemetry.
3. Click **Calibrate sensor** and keep the sensor/head still for ~6 seconds. Then look straight ahead until paired host calibration and head neutral calibration complete. Confirm FUSED and calibrated in diagnostics.
4. Verify one small pitch/yaw/roll at a time. Correct the signed mounting basis if directions differ. Reapply and recalibrate after mounting changes. For example `-yaw,pitch,roll` represents a particular 90° basis rotation; it is not a universal mounting recommendation.
5. For automatic context selection, enter your real task description, mark hands occupied if appropriate, choose the microphone, enable camera, then click **Calibrate for 20s**. Keep the page open and use typical ambient conditions. Recording commands are disabled until calibration releases the microphone.
6. IMU-only control is deliberately brief because this firmware has no absolute yaw reference. Reacquire the webcam rather than accepting unlimited gyro drift.

Relevant endpoints: `/hardware/ports`, `/hardware/connect`, `/hardware/calibrate`, `/system/context-shift/calibrate`, `/system/context-shift/stop`, `/system/state`. Existing HEAD/HAND envelopes and agent endpoints remain intact.

## Physical evidence and remaining checks

Windows enumerated **COM7** during this session. The user confirmed a headset-mounted sensor. A passive 12-second probe received no confirmed V1 signature or decoded samples; a documented `s` status probe still yielded no valid V1 status/telemetry (one malformed response). `IMU_PROBE.json` records this. This proves neither the firmware identity nor sensor health. No firmware was flashed, and the unverified port was not enabled in the live gesture pipeline. **Physical fusion remains unverified.**

- [ ] Confirm Arduino build/flash of the preserved firmware, correct board/core selection, sensor wiring and recognized WHO_AM_I.
- [ ] Observe exact V1 signature, calibrated status and ~50 Hz CSV from the enumerated port. Resolve any non-V1 response before enabling fusion.
- [ ] Validate mounting signs with separate pitch/yaw/roll motions and confirm no unexpected axis coupling.
- [ ] Keep still for firmware and paired host calibration; confirm FUSED with fresh sample ages.
- [ ] Verify all six real head gestures once per held movement; no duplicates from simultaneous sensors.
- [ ] Cover the webcam briefly: observe IMU_ONLY, then timeout suppression; restore webcam and verify safe reanchoring.
- [ ] Unplug/reconnect the Pico, reset its clock, interrupt telemetry and recalibrate: verify immediate suppression/fallback and no stale replay.
- [ ] Test yaw drift while stationary and under translation; confirm disagreement drops IMU rather than moving the browser unsafely.
- [ ] Test hand scrolling, pinch-click and pinch-zoom transitions in a real KiCanvas canvas.
- [ ] Speak short commands: confirm automatic safe execution, clarification on ambiguity and retained approval for consequential actions.
- [ ] Exercise occupied-hands context, text-entry focus, camera loss, microphone failure and manual override through the full 20-second calibration UI.

## Exact files changed or added in this request

Paths are relative to integrated; originals remain unchanged.

| Files | Purpose |
|---|---|
| backend/motion.py; backend/pico_imu.py | Serial input, actual firmware decoder, timestamp/mounting calibration, one fused pose |
| backend/context_shift.py; backend/modality.py | 20-second threshold policy, explicit auto switching, conflict suppression |
| backend/camera_runtime.py | Single recognizer integration, capture timestamps, IMU fallback on camera failure |
| backend/vision/hand_scroll.py; backend/vision/hand_tracker.py | Deliberate two-finger hand scrolling and hand-ready signal |
| backend/audio_capture.py; backend/voice/voice_input.py | Early-ending utterance capture with opening words retained |
| backend/integration.py; backend/skills/kicanvas_skill.py | Hardware/auto APIs, immediate safe voice jobs, read-only search confirmation removal |
| extension/background.js; extension/content.js; extension/gestures.js | Immediate job wake, text-entry context, hand scroll execution |
| frontend/src/components/LiveConsole.tsx; LiveView.tsx; control-dashboard.css | Auto calibration, hardware setup, fusion status and fast voice UI |
| tests/test_motion_context.py; tests/test_input_reliability.py; tests/test_integration.py | Simulated fusion, real-format parser, auto policy, VAD and integration regressions |
| extension/tests/integration.test.cjs; frontend/src/components/LiveConsole.test.tsx | Browser hand-scroll regression and updated approval selector |
| scripts/probe_imu.py; IMU_PROBE.json | Reproducible real-device probe and evidence |
| scripts/smoke_backend.py | Updated the served-page assertion for ContextSwitch branding |
| hardware/firmware/sketch_sep19b.ino; SOURCE_HASHES.json | Unmodified discovered firmware snapshot and preservation hash |
| requirements-imu.txt; requirements-hardware.txt; requirements.lock.txt; .env.example | Optional serial dependencies and configuration |
| MOTION_INTEGRATION_REPORT.md; README.md; INTEGRATION_AUDIT.md; INTEGRATION_REPORT.md | Setup, decisions, evidence, exact scope and manual verification |

`frontend/dist/` and `extension/ui/` were rebuilt from the current source. Test counts/results are also recorded in INTEGRATION_REPORT.md.

## Final automated results

- 60 backend pytest tests passed (including simulated timestamp/mounting/calibration/drift/dropout/reconnect/fusion and real-format V1 parser tests).
- 36 original voice unittest regressions passed.
- 9 extension Node tests passed, including hand-scroll cancellation and unchanged head mappings.
- 10 frontend Vitest tests passed; TypeScript checking and both production builds passed.
- All 171 imported source hashes match. No original team files or discovered firmware were modified.
- IMU samples in unit tests are explicitly simulated; the COM7 probe did not establish physical V1 telemetry or fused gesture success.
