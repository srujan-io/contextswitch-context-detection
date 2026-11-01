# Member 3 action contract proposal

This is a proposal pending a team sync. Names and transport should be frozen with Members 2 and 4 before integration.

The first showcase is the KiCad schematic workflow in `kicad.md`. KiCad actions below are scoped to profile `PCB_WEB` on site type `KICAD_SCHEMATIC`.

## Action envelope

| Field | Type | Rule |
|---|---|---|
| `type` | string | `ACTION` |
| `source` | string | `VOICE` or `AGENT` |
| `action` | string | Must be in the allowlist below |
| `profile` | string | Active profile at dispatch time |
| `parameters` | object | Exact key set and types defined per action |
| `request_id` | string | Unique per request; replay returns stored result and does not execute again |

## Action vocabulary proposal

| Action | Parameters | Profiles / site types | Effect |
|---|---|---|---|
| `SCROLL_UP`, `SCROLL_DOWN` | none | `DOCUMENTATION` on `PDF`/`DOCUMENTATION`; `MAINTENANCE` on `INDUSTRIAL_DASHBOARD` | Read-only navigation |
| `NEXT_SECTION`, `PREVIOUS_SECTION` | none | `DOCUMENTATION` on `PDF`/`DOCUMENTATION` | Read-only navigation |
| `NEXT_PANEL`, `PREVIOUS_PANEL` | none | `MAINTENANCE` on `INDUSTRIAL_DASHBOARD` | Read-only navigation |
| `SHOW_MACHINE` | `machine_id: string` | `MAINTENANCE` on `INDUSTRIAL_DASHBOARD` | Read-only lookup/navigation |
| `OPEN_GUIDE` | `fault_type: string` | `MAINTENANCE` on `INDUSTRIAL_DASHBOARD`; `DOCUMENTATION` on `DOCUMENTATION` | Read-only navigation |
| `PREPARE_FAULT_RECORD` | `machine_id: string`, `fault_type: string`, `notes: string` | `MAINTENANCE` on `INDUSTRIAL_DASHBOARD` | Prepare draft; no submission |
| `SUBMIT_FAULT_RECORD` | `record_id: string`, `approved: bool` | `MAINTENANCE` on `INDUSTRIAL_DASHBOARD` | Consequential; explicit approval required |
| `PAUSE`, `RESUME` | none | Any listed profile/site | Local control state |
| `LOCATE_COMPONENT` | `component_ref: string` | `PCB_WEB` on `KICAD_SCHEMATIC` | Focus viewer on component |
| `EXPLAIN_COMPONENT` | `component_ref: string` | `PCB_WEB` on `KICAD_SCHEMATIC` | Explain using schematic facts |
| `TRACE_SIGNAL` | `signal_name: string` | `PCB_WEB` on `KICAD_SCHEMATIC` | Trace connectivity from KiCad netlist |
| `OPEN_SHEET` | `sheet_id: string` | `PCB_WEB` on `KICAD_SCHEMATIC` | Open hierarchical sheet |
| `RETURN_MAIN_SHEET` | none | `PCB_WEB` on `KICAD_SCHEMATIC` | Return to root schematic |
| `SHOW_ASSEMBLY_CHECKLIST` | `section_id: string` | `PCB_WEB` on `KICAD_SCHEMATIC` | Show section checklist |
| `MARK_COMPONENT_COMPLETE` | `component_ref: string` | `PCB_WEB` on `KICAD_SCHEMATIC` | Update checklist progress |
| `GUIDE_TROUBLESHOOTING` | `issue: string` | `PCB_WEB` on `KICAD_SCHEMATIC` | Suggest checks; do not assert unmeasured faults |
| `SHOW_SCHEMATIC_SECTION` | `section_id: string` | `PCB_WEB` on `KICAD_SCHEMATIC` | Navigate to named region |

## Result envelope

| Field | Type | Meaning |
|---|---|---|
| `type` | string | `ACTION_RESULT` |
| `request_id` | string | Matches the request |
| `success` | boolean | Whether the action completed |
| `message` | string | Short user-readable outcome |
| `reason` | string or null | Failure code when unsuccessful |

Initial failure codes: `PAUSED`, `UNSUPPORTED_PAGE`, `DISCONNECTED`, `INVALID_ACTION`, `INVALID_ARGS`, `DOM_TARGET_FAILED`, `APPROVAL_REQUIRED`, `AMBIGUOUS`, `REJECTED`.

KiCad component explanations and signal tracing must use schematic/netlist data. Component-purpose statements must distinguish facts from inferred design intent, troubleshooting should suggest measurements rather than diagnose without them, and an assembly sequence should be checked against the actual BOM/process.

## Voice event proposal

Emit recognized speech as `{"type":"VOICE_EVENT","text":"...","status":"TRANSCRIBED"}` with a timestamp once transport is agreed. The local router handles clear low-risk phrases deterministically. Complex requests are forwarded to the planner; ambiguous and unrecognized requests are not executed.

## Voice health status event

The voice process emits a `STATUS` event at startup, whenever its status metadata changes, and as a heartbeat every fifteen seconds by default. Before the first utterance, the reason is `NO_UTTERANCE_YET`:

```json
{"source":"VOICE","type":"STATUS","text":"","timestamp":0,"metadata":{"quality":"GOOD","noise_level":"UNKNOWN","noise_ratio":null,"failure_count_in_window":0,"reason":"NO_UTTERANCE_YET"}}
```

`quality` is `GOOD`, `UNCERTAIN`, or `UNAVAILABLE`. `noise_level` is `LOW`, `MED`, `HIGH`, or `UNKNOWN`. Noise remains `UNKNOWN` with a null ratio until a quiet-room RMS baseline and bucket thresholds are manually calibrated and `VOICE_THRESHOLDS_CALIBRATED=true`. The failure count is the number of failed speech attempts in the configured recent-attempt window; it does not include microphone failures or ASR service/network errors. An individual unrecognized utterance does not by itself change `GOOD` to `UNCERTAIN`. The voice process also appends these status events to `data/logs/voice_status.jsonl` so status history is retained during ASR outages. Transport to the shared backend remains pending agreement; current delivery is stdout plus this local JSONL log.
