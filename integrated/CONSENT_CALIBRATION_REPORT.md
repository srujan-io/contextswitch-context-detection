# ContextSwitch consent and environment calibration

Build: `contextswitch-2026.11.01.7`; extension 1.3.0.

## Permission flow

The extension popup first shows an explicit consent screen. The user chooses KiCanvas and/or YouTube, then selects **Allow selected sites & start**, or **Not now**. Chrome's optional host-permission request is made directly from this click handler. The live UI is not mounted until consent is granted and checked against Chrome permissions.

The manifest no longer asks for `<all_urls>` or blanket tab metadata permission and has no static content scripts. Only local backend access is required at installation. Selected sites use optional host permissions and dynamically registered scripts. Before consent, worker tests verify no backend polling, WebSocket creation, page-context messages or browser actions occur. Permission is remembered and checked on worker startup. No user permission dialog was automatically accepted during implementation.

**Revoke access** stops the browser connection, unregisters scripts, disables existing page handlers, cancels pending KiCanvas searches, clears tab context/previews and cancels queued/in-flight jobs. Cleanup targets are retained if the backend is offline and cleared before later execution can resume. The worker checks consent again after async boundaries to avoid dispatching an action after revocation. Already completed actions cannot be undone by revocation.

Camera/microphone access through the local backend is separate from webpage access. Device capture starts only through explicit device controls or calibration. A local backend camera already enabled in an existing session is not a new Chrome site-permission grant. The consent screen explains what page context is read, local backend routing, optional Gemini planning, and spoken-command transcription through Google Web Speech.

Chrome references used: [optional permissions](https://developer.chrome.com/docs/extensions/develop/concepts/declare-permissions), [dynamic content scripts](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts).

## Fifteen-second assessment

No `calibration.py` was found in the supplied folders or Downloads search. The existing `backend/voice/calibrate_voice_noise.py` quiet/noisy RMS method informed this implementation; no missing teammate module is claimed. The shared camera/audio calibration lasts approximately **15 seconds**:

1. **0–5 seconds:** stay quiet and look straight ahead. Measure the median ambient baseline RMS.
2. **5–10 seconds:** speak a short sentence at normal volume and show both hands. Measure the 95th-percentile voice-phase RMS and actual maximum PCM peak amplitude.
3. **10–15 seconds:** show both hands fully, then assume the working posture described in the task field.

Only RMS/peak numbers and tracking/hand-availability evidence are retained; calibration media is not saved or sent for transcription. Measurement windows are bounded so high callback rates do not evict the quiet baseline. Normal spoken commands still use the existing Google transcription path.

The local policy derives a noise threshold from baseline and speech peak, uses voice/background contrast and clipping checks for voice reliability, and uses measured head/hand availability for the camera. UI results expose baseline RMS, speech RMS peak, actual amplitude peak, voice/noise ratio, count of fully visible hands, countdown and current instruction. Missing microphones/cameras remain explicitly unavailable; calibration does not fabricate successful sensor checks.

## Two-hand availability and occupation estimate

MediaPipe tracks up to two hands. All 21 landmarks must fall inside a small frame margin to count a hand as fully visible. Closed-finger/grasp-like poses are labeled **possibly occupied**, not confirmed object use. Both full hands and an available control pose are required before automatic HAND selection. The user's occupied-hands checkbox and task description override the heuristic. Incomplete framing or two possibly occupied hands favors HEAD/VOICE/TYPED according to actual sensor reliability. Unsafe hand actions are suppressed immediately without waiting for mode-switch dwell.

Manual single-hand control remains available outside automatic mode when the selected hand is fully visible. The primary hand is kept by handedness label to prevent cursor jumps when detection ordering changes. Switching the primary hand cancels a pending pinch/zoom/scroll state.

## Using the update

1. Reload ContextSwitch at `chrome://extensions`, then refresh previously open KiCanvas/YouTube tabs to remove obsolete injected code from older builds.
2. Open the extension icon. Select sites and approve access if comfortable. Declining leaves ContextSwitch stopped. Revoke access from the popup footer at any time.
3. In **Setup & calibration**, choose the microphone and enter task context. Mark hands occupied if appropriate.
4. Click **Calibrate for 15s**. This explicitly enables the camera and samples microphone levels. Follow the three displayed instructions. No browser gestures execute during calibration.
5. Review Environment assessment and the mode/reason. Manual mode selection disables automatic switching. If camera startup or framing fails, fix the device/frame and rerun calibration.

Backend entry point and startup command are unchanged. The delivered extension UI is rebuilt under extension/ui. Chrome's real grant/deny/revoke prompts require a manual browser test; unit tests use explicit Chrome mocks. Physical hand-occupation/object recognition is not claimed.

## Main files

- extension/manifest.json, privacy.js, background.js: optional host permissions, consent, registration, routing/revocation gates.
- extension/content.js, gestures.js, heartbeat.js, kicanvas.js: disable page reads/actions and pending searches on revocation.
- frontend/src/components/ExtensionConsent.tsx, PopupView.tsx, popup.css: consent-first popup and revoke control.
- backend/context_shift.py, vision/hand_availability.py, vision/hand_tracker.py, camera_runtime.py, modality.py: 15-second measurements, two-hand evidence and immediate hand suppression.
- backend/integration.py, execution/manager.py: calibration startup and cancellation of browser jobs on revocation.
- frontend/src/components/LiveConsole.tsx, LiveView.tsx: measured environment results and 15-second instructions.
- tests/test_environment_consent.py; extension/tests/integration.test.cjs; frontend/src/components/ExtensionConsent.test.tsx: calibration, framing, denial and revocation regressions.

Original member snapshots remain unchanged.
