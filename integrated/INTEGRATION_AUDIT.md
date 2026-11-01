# Beyond Touch integration audit

Update: a wider parent-folder search discovered `Downloads/sketch_sep19b/sketch_sep19b.ino`, the actual ContextSwitch Pico/MPU9250 firmware (115200 baud, 50 Hz, seven-column CSV). The latest implementation, protocol, evidence and exact file list are in MOTION_INTEGRATION_REPORT.md. This supersedes earlier missing-firmware findings while preserving the original empty teammate hardware reader.

Discovery date: 2026-11-01. Originals are read-only source snapshots. SOURCE_HASHES.json records every imported source file; bootstrap excludes environments, dependencies, caches, build output and .env files.

## Inventory

| Actual folder under Downloads | Implemented functionality | Gaps |
|---|---|---|
| contextswitch-context-detection/contextswitch-context-detection | FastAPI context store/detector, website skills, Gemini planner, validator, in-memory execution queue; Chrome context collector and KiCanvas shadow DOM component search; four Node regression tests | Key required at import; update makes any tab active; interval-only MV3 polling; no CV |
| contextswitch-cv/contextswitch-cv | MediaPipe task models, face landmark displacement pose, median gesture debounce/calibration, cursor filtering, palm-normalized pinch detection and click; threaded camera and CV WS | No One Euro pose filter, no explicit four-state head enum, no pinch zoom, no camera heartbeat. Tracking loss emits PINCH_END before loss (can click accidentally). hardware/imu_reader.py and config.py are empty |
| contextswitch-kicad_voicecommands/contextswitch-kicad_voicecommands/member3 | Deterministic parser, ground-truth resolver, FastEmbed matcher, Gemini escalation, confirmation, microphone ASR and status | MockExecutor is default; domain actions exceed KiCanvas skill; fixture catalog is not live browser context; microphone unverified |
| screenshot-to-soul-5020-main/screenshot-to-soul-5020-main | React/TanStack frontend with isolated simulation and extension bridge | Live backend controls incomplete |
| contextswitch-frontend | Additional React frontend snapshot; pickModality is explicitly simulation-only | No actual Member 2 sensor backend found |
| contextswitch/contextswitch and contextswitch/screenshot-to-soul-5020 | Additional agent/extension/frontend integration attempt with CV bridge tests and popup build | Bridge drops cursor events, connects only with popup open, forwards only to UI; no browser gestures or SENSOR_STATUS |

## Contracts and decisions

Agent endpoints retained: /context/update (top-level integer tab_id), /context/active, /context/activate/{tab_id}, /skills/active, /skills/validate-action, /planner/create-plan, /actions/validate, /actions/dispatch, /actions/next?tab_id, /actions/result, /actions/jobs/{job_id}.

HEAD/HAND wire events retain source/action/parameters/timestamp; translator maps SCROLL_UP/DOWN, PREVIOUS/NEXT_PAGE, ZOOM_OUT/IN to HEAD_UP/DOWN/LEFT/RIGHT/TILT_LEFT/TILT_RIGHT. Existing browser behavior maps yaw to canvas horizontal pan; this deliberate source behavior is retained rather than navigating away from a schematic.

Dispatch revalidates skill targets and parameters; search_component requires explicit approval. Only verified SUCCESS completes a job. Synthetic wheel/double click remains UNVERIFIED. No arbitrary script execution accepted.

Use original agent package layout under backend (absolute imports preserved by documented --app-dir backend). Reuse the more complete React popup from contextswitch/screenshot-to-soul-5020. Merge agent content collector + KiCanvas executor with CV content handler. One worker owns CV WS, context synchronization, persistent result outbox, polling and UI bridge. Alarms restart worker; content heartbeat wakes it between alarms. No per-frame Gemini.

No teammate modality backend or implemented IMU firmware/serial contract found in the supplied relevant folders. Add a conservative health/control arbiter as integration code, explicitly not a recovered Member 2 implementation. Recommendations do not switch active mode. Active pinch holds zoom priority; agent lease suppresses all real-time actions for its target; cancellation bypasses selection.

Dependencies: original Python requirements unpinned; CV needs MediaPipe/OpenCV/NumPy; voice optionally PyAudio/FastEmbed; frontend uses React 19/Vite 8/Node 22+. Keep optional hardware dependencies separate. Gemini SDK import and client creation become lazy; missing credentials must not break deterministic commands or camera.

## Baseline and risks

Original agent extension: 4/4 Node tests pass. Initial Python invocation fails (Windows Store alias); installed CPython 3.11 located, dependencies absent. Run voice tests with bytecode disabled to leave originals unchanged. Browser/hardware tests require actual devices and Chrome; automated stubs are not live evidence. Single process queue is intentionally ephemeral; ambiguous in-flight actions must fail without automatic replay after timeout/restart.

Implementation sequence: safe source copy; backend lazy planner + command adapters + camera worker/health; merged worker and gestures; live React console; focused regression tests; setup scripts and truthful verification checklist.
