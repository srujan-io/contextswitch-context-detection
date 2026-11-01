# Integration report — 2026-11-01

Latest build contextswitch-2026.11.01.8: automatic VOICE↔HAND handover now prioritizes fully visible control-ready hands, releases HAND immediately on loss/cropping/occupancy, and preserves calibrated voice readiness during idle periods. Head/typed remain fallback when voice is unavailable. Added AUTO selection to resume an already completed assessment without rerecording calibration. MediaPipe remains configured for two hands; the preview now renders both hands instead of only the pointer owner. Four new regression tests cover handover, idle voice readiness, fallback and two-hand rendering. Voice remains record-on-request.

Latest build: contextswitch-2026.11.01.7, extension 1.3.0. Consent-first popup, optional per-site permissions and revocation cancellation replace automatic page injection. Environment assessment now uses a shared 15-second audio baseline/peak and two-hand visibility/pose session. Exact behavior and limitations: CONSENT_CALIBRATION_REPORT.md. No calibration.py was present; the existing calibrate_voice_noise.py RMS method was adapted.

Latest camera recovery: live diagnostics showed valid face tracking but WAITING_FOR_RELEASE with pitch ~14° from neutral. Calibration now uses a stable timed hold (1.2 seconds, minimum eight valid samples) rather than requiring 20 frames; explicit recenter includes a two-second positioning delay. The same camera supplies an opt-in ephemeral JPEG preview, calibration progress and processing diagnostics. No extra camera stream is opened and no preview image is saved. Backend build: contextswitch-2026.11.01.6. New low-FPS, fast-burst and movement-reset calibration regressions pass.

## Latest motion/context update

Build `contextswitch-2026.11.01.5` adds two-finger hand scroll, early-ending voice capture with immediate validated safe-command dispatch, opt-in 20-second audio/visual/task-context calibration, automatic mode selection, and a unified serial/webcam pose producer. Actual firmware was found in Downloads/sketch_sep19b/sketch_sep19b.ino (50 Hz / 115200 baud / V1 CSV), superseding earlier missing-firmware notes. All 171 imported source hashes remain unchanged.

Full exact file list, setup commands, protocol, calibration instructions, serial-probe evidence and real-hardware checklist: **MOTION_INTEGRATION_REPORT.md**. COM7 was enumerated and probed, but no valid V1 signature/telemetry was confirmed. Physical fusion remains unverified and the port is not silently enabled in live control.

Final motion-update checks: **60 backend + 36 voice + 9 extension + 10 frontend tests passed (115 total)**; TypeScript and both production builds passed. Unit fusion input is simulated. Original preservation: 171 matching hashes.

## Follow-up input reliability fixes

After the user's live trial reported head gestures firing once then failing and unclear headset transcription:

- Normalized eye-line roll modulo 180° to prevent neutral +179/-179 discontinuities; added adaptive One Euro pose filtering and finite-angle guards.
- Added explicit head recenter, live head delta/calibration/state diagnostics, a stable neutral release before rearming, and ambiguous-axis suppression. Live ergonomics still require user verification; synthetic regressions cover repeat firing after return to center.
- Added explicit headset device selection and recognition-language controls. The popup now records a bounded five-second window, with Recording/Transcribing phases, rather than consuming the first 400 ms as ambient noise. The original CLI VAD path remains available.
- Added RMS/peak/clipping/duration diagnostics and specific silence/quiet feedback. Captured-but-unrecognized speech is separated from unavailable microphone hardware; recognized text is preserved when planning fails.
- Added six input reliability tests. Test configuration now explicitly sets a blank Gemini key, preventing local .env credentials from being used by regressions. Before this correction, a test inadvertently made one successful real Gemini plan request; it executed no browser actions.

Updated totals: 36 backend pytest tests, 36 voice unittest tests, eight extension Node tests and ten frontend tests; TypeScript and both production builds checked. These checks do not replace a live headset transcription and head-gesture retest.

## Delivered

The application is in this integrated directory, with one backend entry point (`integration:app`, port 8001), one merged MV3 extension (`extension/manifest.json`, `background.js`, `content.js`, `gestures.js`, `kicanvas.js`), and a built React live console available both as popup and backend-served frontend. The original frontend's visual system and simulation source are preserved; live operation does not consume simulation events.

Source inventory and conflicts are in INTEGRATION_AUDIT.md. SOURCE_HASHES.json plus scripts/verify_sources.cjs verify the 170 imported original files remain unchanged. No original folder was reorganized, no environments or secrets were copied, and no Git commits or pushes were made.

## Integration behavior

- Reused the source face/hand trackers, model assets, calibration, median gesture recognition, cursor filter, pinch detection, deterministic voice parser, resolver/ranker modules, microphone recognizer, context detector, website skills, validator, execution manager and KiCanvas shadow DOM search.
- Added a threaded camera adapter with pause/resume, explicit cancellation, real sensor status transitions and approximately 1500 ms heartbeat. Optional camera/import/device failures leave the backend running. A recovery requires fresh calibration. No duplicate camera server runs.
- Added a palm-normalized pinch-zoom recognizer with IDLE/ARMING/ACTIVE/RELEASING states. It cancels a pending click before zoom. Stable short pinches retain click behavior; loss cancels without clicking.
- Added conservative arbitration because an actual Member 2 sensor backend was absent. Active selection and recommendation are separate. Camera timeout/loss/pause suppresses actions immediately. Hand zoom suppresses head zoom; queued/running agent work suppresses real-time controls for that tab. No confidence measurements or automatic switches are invented.
- Deterministic typed and recognized voice commands create previewed plans using the same original parser. Supported mappings feed the actual validated action queue, never MockExecutor. Contextual/multi-step commands reach the preserved Gemini planner. Its client is lazy, so absent credentials do not stop other features. The original semantic matcher is an optional route with explicit confirmation for escalated suggestions; its fixture catalog limits applicability.
- Preview IDs bind approval to the plan, tab and URL, expire after 120 seconds for execution, and prevent duplicate submission through the console. Dispatch validates again. Actions carry an expected URL so navigating after approval fails rather than acting on a different page. Arbitrary web origins cannot submit local approval requests.
- The worker owns WS, context synchronization, tab-targeted claims, cancellation, durable attempt markers and result outbox. Alarms and content heartbeat supplement interval polling and Chrome WS keepalive. Result uploads are idempotent. Timeout fails without replay. Backend restart discards old queues and previews.
- Synthetic wheel/double-click dispatch remains UNVERIFIED. KiCanvas component selection is verified only through observable selected item and enabled viewer control. UNVERIFIED halts later steps and becomes NEEDS_REVIEW; SUCCESS without verification is downgraded. The UI shows this distinction, not generic success.
- KiCanvas gesture targets and pointer hit testing now traverse shadow DOM. Legacy yaw events retain horizontal canvas pan rather than changing browser history.

## Evidence

| Check | Result and scope |
|---|---|
| Original Python voice baseline | 36/36 unittest tests passed; bytecode disabled when running originals |
| Original context extension baseline | 4/4 Node tests passed |
| Additional source integration bridge baseline | 6/6 Node tests passed (includes same four KiCanvas tests) |
| Integrated backend | 30 pytest tests passed: six mappings and held/released/jitter recognition, approval, context routing/invalidation, validation, idempotence, unknown-result handling, timeouts, sensor priority/staleness, pause/reconnect, absent hardware, typed and voice adapters, mocked semantic/Gemini routing and origin boundary |
| Integrated extension | 8 Node tests passed: four original KiCanvas tests and four new VM browser-adapter tests covering six mappings, click cancellation/zoom, tab routing, stale events, reconnect and durable deduplication |
| Reused and integrated frontend | 10 Vitest tests passed, including live explicit approval and disconnected status tests |
| TypeScript | `npm run typecheck` passed |
| Production builds | `npm run build` and `npm run build:extension` passed |
| Real HTTP smoke | Backend process startup, frontend serving, typed preview/dispatch, unverified result and process restart with no stale replay passed |
| Real camera probe | One actual frame captured; both bundled MediaPipe models loaded and processed it; head RECOVERING, no hand detected on that frame. This is not a gesture accuracy trial |
| Real microphone probe | Actual 200 ms capture succeeded, 16384 bytes captured, no retained media or network ASR request. Transcription remains unverified |
| Source preservation | All 170 imported source hashes matched after integration |

Automated hardware-failure tests, hand/head measurements, Chrome APIs, Gemini and semantic outputs use explicit test doubles. VM extension tests are not proof of a loaded Chrome extension or a successful real KiCanvas interaction. See HARDWARE_PROBE.json for device evidence. No real Gemini request was made because no key was supplied to integration.

Windows sandbox blocked asyncio socketpair creation and some Vitest temporary-file renames. Those checks passed when rerun with approved normal Windows execution. Initial Python Store alias was unusable; testing used installed CPython 3.11.9. Runtime warnings remain: Starlette recommends its newer HTTP test client, and the frontend's existing dependency graph emits a Node punycode deprecation warning. Neither failed checks.

## Remaining manual demo checks and limits

- [ ] Load the built extension in Chrome 120+, refresh a real KiCanvas schematic, confirm correct active title/tab across two browser tabs/windows.
- [ ] Test actual head pitch/yaw/roll directions, neutral calibration, jitter, tracking loss/recovery, camera pause/resume and webcam removal. The supplied pose is landmark displacement, not a physical six-degree pose; no supplied One Euro pose filter was found. The existing held/released recognizer uses flags rather than a named four-state enum.
- [ ] Test pointer across shadow DOM controls, brief pinch click, held-pinch aperture zoom and opening/releasing without accidental clicks. Tune thresholds for the user's hand/camera distance. The new zoom recognizer has synthetic-measurement tests, not live ergonomic verification.
- [ ] Use an actual current-sheet reference in KiCanvas. Confirm selected-item evidence and visually inspect requested zoom. Zoom, pan and details currently have no reliable canvas-state verification and remain UNVERIFIED. Signal tracing, assembly workflows and arbitrary native software actions have no implemented browser executor.
- [ ] Say a command into the actual microphone, confirm transcript accuracy and plan route. Audio capture succeeded locally, but end-to-end Google ASR/network behavior was not exercised. PortAudio errors still return typed fallback.
- [ ] Configure a real backend Gemini key and test contextual multi-step planning and clarification. Reapprove after context changes. Optional FastEmbed semantic routing was adapter-tested with mocks, not a downloaded model inference run.
- [ ] Suspend/restart the MV3 worker from Chrome's extension tools, close/reopen the popup, disconnect/restart backend, and confirm cancellation, wakeup, no duplicate execution and result outbox upload. Automated tests cover the logic, not Chrome's actual scheduling policy. Alarms may delay inactive-page recovery up to 30 seconds.
- [ ] Test an action in flight while switching tabs and navigating the target. Agent work blocks gestures on its target; a changed URL rejects queued execution. No automatic retries are made for uncertain outcomes.
- [ ] IMU cannot be exercised: supplied hardware/imu_reader.py is empty and no firmware, serial format, calibration or sampling rate was found. It remains explicitly UNAVAILABLE; no COM port or fusion behavior is fabricated.

The implementation is ready for these final live browser/device trials. It is not claimed as a fully verified hands-free KiCanvas demo until they pass. The setup and exact procedure are in README.md.
