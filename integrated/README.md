# Beyond Touch / ContextSwitch — integrated Windows demo

Automatic handover update (build contextswitch-2026.11.01.8): finish the 15-second assessment once. Automatic mode prefers two fully visible, control-ready hands, then calibrated voice readiness, then head/typed fallback. Hand loss/cropping releases HAND immediately; returning hands must be stable before control resumes. Choose **Automatic: voice ↔ hands** in the mode selector to resume automation after manual mode selection. **Show camera preview** now draws both recognized hands with separate labels/colors; one hand remains the pointer owner. Voice readiness does not start background recording—use **Speak command**. Real live handover still requires a user trial.

Latest consent/calibration update: extension 1.3.0 now asks for selected-site permission before starting, with **Not now** and **Revoke access** options. Environment calibration is now **15 seconds**, measuring quiet baseline, normal-voice peaks and two-hand framing. See [CONSENT_CALIBRATION_REPORT.md](CONSENT_CALIBRATION_REPORT.md) for consent boundaries, instructions, measured results and limitations. Reload the extension and refresh previously open supported tabs after updating.

Camera recovery update (build contextswitch-2026.11.01.6): **Show camera preview** uses the existing camera stream (no second camera and no saved frames). Recenter gives two seconds to look forward, then requires a stable 1.2-second hold with at least eight valid samples. Progress and processing time are visible. WAITING_FOR_RELEASE means the face is tracked but the previous gesture has not returned to its calibrated neutral pose; recenter if your sitting position changed. Frames are limited to 640-pixel width to reduce processing load.

The Chrome toolbar icon opens a dedicated 400×600 ContextSwitch popup. **Controls** contains live commands and camera/head controls; **Setup & calibration** contains microphone, IMU and automatic-context setup. The arrow in its header opens the full local dashboard. Reload the unpacked extension at chrome://extensions after a build, then pin ContextSwitch from Chrome's Extensions menu to keep the icon visible. Icon vector source and PNGs are in extension/icons; regenerate with `.venv/Scripts/python.exe scripts/create_icons.py` (Pillow required).

Latest hand-scroll, immediate safe voice execution, 20-second automatic context selection and **actual Pico V1 firmware integration** are documented in [MOTION_INTEGRATION_REPORT.md](MOTION_INTEGRATION_REPORT.md). This supersedes earlier missing-IMU notes: the firmware was found in Downloads/sketch_sep19b, outside the named team folders. Physical V1 telemetry/fusion is not yet verified on the attached serial device.

### Input reliability update

Restart the backend, reload the extension at chrome://extensions, then refresh KiCanvas after this update. The popup now includes **Recenter head** and reports CALIBRATING, CANDIDATE, FIRED, WAITING_FOR_RELEASE and tracking loss. Look straight ahead, recenter, and hold still until calibrated. Each gesture fires once; return to center for about 200 ms before the next one. The eye-line roll is normalized across ±180° and pose values use adaptive filtering.

For a headset, click **Find microphones** and choose the headset's **input** (not Stereo Mix, an output, or an unused webcam microphone). Choose en-US/en-IN/en-GB/en-AU as appropriate. Click **Record command (5s)**, wait for **Speak now**, then speak a short command. This path records a fixed window rather than sampling away the beginning as ambient noise. Audio diagnostics distinguish silence, very quiet input and clipping; a failed transcript no longer means the hardware itself is unavailable. Check the headset mute switch and Windows input volume if levels are silent or very quiet.

The originals under Downloads remain source snapshots. This directory is the application. Python 3.11, Node 22.12+ and Chrome 120+ are required. One FastAPI process owns context, planning, validation, the action queue, the optional camera thread, and CV WebSocket on **127.0.0.1:8001**. The React UI works as an extension popup or at the backend root. No second CV server is needed.

## PowerShell setup

From this directory:

```powershell
./scripts/setup.ps1 -Hardware
# If py is unavailable, supply the actual Python 3.11 executable:
# ./scripts/setup.ps1 -Hardware -Python 'C:/path/to/python.exe'
Copy-Item .env.example .env
# Optional: edit .env with a backend-only GEMINI_API_KEY.
./scripts/start.ps1
```

Manual equivalent:

```powershell
py -3.11 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m pip install -r requirements-hardware.txt
Set-Location frontend
npm ci
npm run build
npm run build:extension
Set-Location ..
./.venv/Scripts/python.exe -m uvicorn integration:app --app-dir backend --host 127.0.0.1 --port 8001 --workers 1
```

`requirements.lock.txt` records the exact tested Python environment, including hardware libraries; use `pip install -r requirements.lock.txt` to reproduce that Windows/Python 3.11 environment. `frontend/package-lock.json` fixes frontend dependency versions. Environments/dependencies were freshly installed under integrated, never copied from member snapshots.

The supplied semantic matcher/resolver is preserved under backend/voice. To try its optional live command adapter, install `fastembed>=0.5,<1` and set `BEYOND_TOUCH_SEMANTIC=1`. This can download an embedding model and uses the teammate's sample ground-truth catalog; it is off by default because that catalog may not describe your schematic. Only mapped KiCanvas search/details actions enter the real queue. Other domain actions (assembly checklists, signal tracing, marking complete) have no real browser implementation and are not claimed as integrated. Deterministic commands use the original parser; general or multi-step commands use the contextual Gemini planner.

## Frontend

After building, open http://127.0.0.1:8001/ (served by the same backend). For development, in a second PowerShell terminal:

```powershell
Set-Location frontend
npm run dev
```

Open http://127.0.0.1:5173/. Keep KiCanvas as the last supported active browser context. The extension popup is preferable for controlling the current KiCanvas tab. The popup communicates only with the worker; the standalone UI uses HTTP, with no camera WebSocket. Original simulation components remain available in source and are not used by the live console.

## Chrome and KiCanvas

1. Disable other ContextSwitch/Beyond Touch extensions so only this one can act. Stop separately running teammate CV servers to release the webcam.
2. Open chrome://extensions, enable Developer mode, choose **Load unpacked**, and select this directory's `extension/` folder. Build its UI first. Reload and then refresh KiCanvas whenever extension code changes.
3. Open https://kicanvas.org/ and load a real KiCad schematic with full controls. Enable the Symbols panel. Choose a reference actually present on the current sheet (the supplied automated fixtures use R101; your project may differ).
4. Open the Beyond Touch popup. Verify the title, URL and numeric tab ID. Enable the camera and hold a neutral pose for approximately one second to calibrate. A missing camera is shown as UNAVAILABLE with a reason. Pause/resume is available in the popup.
5. Pitch up/down pans vertically; yaw left/right pans horizontally; roll left/right zooms out/in. The backend retains the six logical SCROLL/PREVIOUS/NEXT/ZOOM mappings and legacy HEAD wire names. Yaw deliberately retains the teammate browser's canvas pan behavior instead of navigating browser history.
6. Move the index fingertip for the virtual cursor. Brief thumb/index pinch and release clicks. For zoom, hold a close pinch for at least 350 ms, then vary aperture while remaining near the hand; open beyond the release threshold to finish. Palm width normalizes aperture. Tracking loss cancels the click. The new zoom recognizer requires live ergonomic tuning; automated tests use synthetic hand measurements.
7. Type **zoom in** or **scroll down**, preview the plan, then Execute. Wheel dispatch is reported **UNVERIFIED**, not successful zoom. Inspect the actual canvas.
8. Type **find R101** using your real reference. Preview, explicitly approve the confirmation-required search, then execute. SUCCESS VERIFIED requires the Symbols item to become selected and KiCanvas's zoom-to-selection control to become enabled; it verifies selection, not the requested zoom itself. A hidden, missing, ambiguous or unconfirmed target fails or remains UNVERIFIED.
9. With a valid backend Gemini key, try **Find R101 and show its details**. Plans remain bounded to registered skills and at most five steps. Missing details cause clarification. An unverified step stops later steps and requires review.
10. Push to talk captures an utterance with the supplied SpeechRecognition pipeline and sends audio to Google Web Speech. Preview/approval/dispatch is the same as typed input. Device access was probed successfully locally; end-to-end spoken transcription is still a manual demo test. If capture/ASR fails, type the command. No key belongs in extension files.

## Verification and troubleshooting

```powershell
./scripts/test.ps1
./.venv/Scripts/python.exe scripts/smoke_backend.py
./.venv/Scripts/python.exe scripts/probe_hardware.py
node scripts/verify_sources.cjs
```

The probe captures one frame and 200 ms of audio without retaining or transmitting media. It does not verify gestures or speech recognition. Backend `/docs` exposes preserved API contracts. `/system/state` exposes real sensor statuses and separate active/recommended controls. No numerical sensor confidence is invented.

Keep the backend bound to loopback and use one worker. Jobs/context/previews are in-memory. A restart invalidates old previews and jobs; no queued gesture or action is persisted for replay. Chrome stores attempted action IDs and a result upload outbox. A result timeout fails the job without replay. Chrome alarms and content heartbeats supplement WS keepalive; actual suspension and restart need the manual checks in INTEGRATION_REPORT.md.

An unknown execution result halts subsequent steps. Re-preview only after inspecting the browser. Missing Gemini credentials affect natural-language planning only. Missing optional hardware does not stop the backend. If PortAudio reports -9999, choose a valid device with BEYOND_TOUCH_MIC_INDEX or keep typed input. No IMU driver or serial format was supplied, so no COM port is assumed and IMU remains unavailable.
