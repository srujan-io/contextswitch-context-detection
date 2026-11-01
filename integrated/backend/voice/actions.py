"""Member 3's dependency-free voice-to-action contract and mock router."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import time
from typing import Any
from uuid import uuid4


ACTION_RULES: dict[str, dict[str, Any]] = {
    "SCROLL_UP": {"parameters": {}, "profiles": {"DOCUMENTATION", "MAINTENANCE", "PCB_WEB"}, "sites": {"PDF", "DOCUMENTATION", "INDUSTRIAL_DASHBOARD", "KICAD_SCHEMATIC"}, "consequential": False},
    "SCROLL_DOWN": {"parameters": {}, "profiles": {"DOCUMENTATION", "MAINTENANCE", "PCB_WEB"}, "sites": {"PDF", "DOCUMENTATION", "INDUSTRIAL_DASHBOARD", "KICAD_SCHEMATIC"}, "consequential": False},
    "NEXT_PANEL": {"parameters": {}, "profiles": {"MAINTENANCE"}, "sites": {"INDUSTRIAL_DASHBOARD"}, "consequential": False},
    "PREVIOUS_PANEL": {"parameters": {}, "profiles": {"MAINTENANCE"}, "sites": {"INDUSTRIAL_DASHBOARD"}, "consequential": False},
    "NEXT_SECTION": {"parameters": {}, "profiles": {"DOCUMENTATION"}, "sites": {"PDF", "DOCUMENTATION"}, "consequential": False},
    "PREVIOUS_SECTION": {"parameters": {}, "profiles": {"DOCUMENTATION"}, "sites": {"PDF", "DOCUMENTATION"}, "consequential": False},
    "SHOW_MACHINE": {"parameters": {"machine_id": str}, "profiles": {"MAINTENANCE"}, "sites": {"INDUSTRIAL_DASHBOARD"}, "consequential": False},
    "OPEN_GUIDE": {"parameters": {"fault_type": str}, "profiles": {"MAINTENANCE"}, "sites": {"INDUSTRIAL_DASHBOARD", "DOCUMENTATION"}, "consequential": False},
    "PREPARE_FAULT_RECORD": {"parameters": {"machine_id": str, "fault_type": str, "notes": str}, "profiles": {"MAINTENANCE"}, "sites": {"INDUSTRIAL_DASHBOARD"}, "consequential": False},
    "SUBMIT_FAULT_RECORD": {"parameters": {"record_id": str, "approved": bool}, "profiles": {"MAINTENANCE"}, "sites": {"INDUSTRIAL_DASHBOARD"}, "consequential": True},
    "LOCATE_COMPONENT": {"parameters": {"component_ref": str}, "profiles": {"PCB_WEB"}, "sites": {"KICAD_SCHEMATIC"}, "consequential": False},
    "EXPLAIN_COMPONENT": {"parameters": {"component_ref": str}, "profiles": {"PCB_WEB"}, "sites": {"KICAD_SCHEMATIC"}, "consequential": False},
    "TRACE_SIGNAL": {"parameters": {"signal_name": str}, "profiles": {"PCB_WEB"}, "sites": {"KICAD_SCHEMATIC"}, "consequential": False},
    "OPEN_SHEET": {"parameters": {"sheet_id": str}, "profiles": {"PCB_WEB"}, "sites": {"KICAD_SCHEMATIC"}, "consequential": False},
    "RETURN_MAIN_SHEET": {"parameters": {}, "profiles": {"PCB_WEB"}, "sites": {"KICAD_SCHEMATIC"}, "consequential": False},
    "SHOW_ASSEMBLY_CHECKLIST": {"parameters": {"section_id": str}, "profiles": {"PCB_WEB"}, "sites": {"KICAD_SCHEMATIC"}, "consequential": False},
    "MARK_COMPONENT_COMPLETE": {"parameters": {"component_ref": str}, "profiles": {"PCB_WEB"}, "sites": {"KICAD_SCHEMATIC"}, "consequential": False},
    "GUIDE_TROUBLESHOOTING": {"parameters": {"issue": str}, "profiles": {"PCB_WEB"}, "sites": {"KICAD_SCHEMATIC"}, "consequential": False},
    "SHOW_SCHEMATIC_SECTION": {"parameters": {"section_id": str}, "profiles": {"PCB_WEB"}, "sites": {"KICAD_SCHEMATIC"}, "consequential": False},
    "PAUSE": {"parameters": {}, "profiles": {"DOCUMENTATION", "MAINTENANCE", "PCB_WEB"}, "sites": {"PDF", "DOCUMENTATION", "INDUSTRIAL_DASHBOARD", "KICAD_SCHEMATIC"}, "consequential": False},
    "RESUME": {"parameters": {}, "profiles": {"DOCUMENTATION", "MAINTENANCE", "PCB_WEB"}, "sites": {"PDF", "DOCUMENTATION", "INDUSTRIAL_DASHBOARD", "KICAD_SCHEMATIC"}, "consequential": False},
}


@dataclass(frozen=True)
class Action:
    type: str
    source: str
    action: str
    profile: str
    parameters: dict[str, Any]
    request_id: str


@dataclass(frozen=True)
class ActionResult:
    type: str
    request_id: str
    success: bool
    message: str
    reason: str | None = None


def normalize(text: str) -> str:
    value = text.lower().replace("’", "'").strip()
    value = re.sub(r"[^\w\s']", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value.replace("don't", "do not")


def classify(text: str) -> tuple[str, str | None]:
    """Return (simple|complex|ambiguous|rejected, action name if simple)."""
    kind, name, _ = parse_intent(text)
    return kind, name


_COMPONENT_REF = r"(?:tp|[rcj])\s*[-_]?\s*\d{2,4}[a-z]?"


def canonical_component_ref(reference: str) -> str | None:
    """Join common ASR gaps and separators inside a KiCad reference only."""
    compact = re.sub(r"[\s_-]+", "", reference).upper()
    if re.fullmatch(r"(?:TP|[RCJ])\d{2,4}[A-Z]?", compact):
        return compact
    return None


def parse_intent(text: str) -> tuple[str, str | None, dict[str, Any]]:
    """Classify a transcript and extract typed arguments for supported commands."""
    value = normalize(text)
    # Preserve the generic navigation commands before the broader sheet parser.
    primary = {"go to next panel": "NEXT_PANEL", "next panel": "NEXT_PANEL",
               "previous panel": "PREVIOUS_PANEL", "go to previous panel": "PREVIOUS_PANEL"}
    if value in primary:
        return "simple", primary[value], {}
    # More than one natural phrase maps to each supported KiCad intent. Keep
    # identifier normalization local to references; don't rewrite normal text.
    patterns = [
        (rf"(?:locate|find|where is|where's|show me|focus on|take me to)\s+(?:the\s+)?(?:component\s+)?({_COMPONENT_REF})(?:\s+.*)?", "LOCATE_COMPONENT", "component_ref"),
        (rf"(?:what does|explain|describe|tell me about|what is the purpose of|what's the purpose of|purpose of|what is)\s+({_COMPONENT_REF})(?:\s+(?:do|used for))?", "EXPLAIN_COMPONENT", "component_ref"),
        (rf"(?:mark|set)\s+({_COMPONENT_REF})\s+(?:as\s+)?(?:complete|done)|(?:check off|complete|finish)\s+({_COMPONENT_REF})", "MARK_COMPONENT_COMPLETE", "component_ref"),
        (r"(?:trace|follow|track)\s+(?:the\s+)?(.+?)(?:\s+(?:signal|net|connections?))?$", "TRACE_SIGNAL", "signal_name"),
        (r"(?:open|go to|navigate to|switch to|show sheet)\s+(?:the\s+)?(.+?)(?:\s+sheet)?$", "OPEN_SHEET", "sheet_id"),
        (r"(?:i am|i'm|i am currently) assembling (?:the\s+)?(.+?)(?:\s+section)?$", "SHOW_ASSEMBLY_CHECKLIST", "section_id"),
        (r"(?:show|open|display) (?:the\s+)?(?:assembly )?checklist for (?:the\s+)?(.+?)(?:\s+section)?$", "SHOW_ASSEMBLY_CHECKLIST", "section_id"),
        (r"(?:my board (?:isn't|is not|won't|will not)|i (?:can't|cannot|am having trouble|have trouble)\s+with|troubleshoot|help me troubleshoot|help diagnose)\s+(.+)$", "GUIDE_TROUBLESHOOTING", "issue"),
        (r"(?:show me|show|open|display|focus on)\s+(?:the\s+)?(.+?)\s+(?:section|area|part)$", "SHOW_SCHEMATIC_SECTION", "section_id"),
    ]
    for pattern, action, parameter in patterns:
        match = re.fullmatch(pattern, value)
        if match:
            captured = next((group for group in match.groups() if group), "")
            argument = captured.strip().upper()
            if parameter == "component_ref":
                canonical = canonical_component_ref(captured)
                if not canonical:
                    continue
                argument = canonical
            if parameter == "sheet_id":
                aliases = {
                    "THE 3 3 VOLT REGULATOR": "2_5Vto3.3VRegulator",
                    "3 3 VOLT REGULATOR": "2_5Vto3.3VRegulator",
                    "THE SAMD21": "3_uC_SAMD21",
                    "SAMD21": "3_uC_SAMD21",
                }
                argument = aliases.get(argument, argument)
            if action == "SHOW_ASSEMBLY_CHECKLIST":
                argument = argument.removesuffix(" SECTION").strip()
            return "simple", action, {parameter: argument}
    signal_match = re.fullmatch(r"where do (.+) go", value)
    if signal_match:
        signal = signal_match.group(1).upper()
        if "USB" in signal:
            signal = "USB_P, USB_N"
        return "simple", "TRACE_SIGNAL", {"signal_name": signal}
    if value in {"return to the main schematic", "return to main schematic", "go back to the main schematic",
                 "go back to main schematic", "return to root schematic", "back to the root schematic",
                 "open the main schematic", "take me back to the main schematic"}:
        return "simple", "RETURN_MAIN_SHEET", {}
    exact = {
        "scroll down": "SCROLL_DOWN", "scroll down please": "SCROLL_DOWN", "page down": "SCROLL_DOWN",
        "scroll up": "SCROLL_UP", "scroll up please": "SCROLL_UP", "page up": "SCROLL_UP",
        "next panel": "NEXT_PANEL", "go to next panel": "NEXT_PANEL", "previous panel": "PREVIOUS_PANEL",
        "previous panel please": "PREVIOUS_PANEL", "next section": "NEXT_SECTION", "previous section": "PREVIOUS_SECTION",
        "pause": "PAUSE", "pause controls": "PAUSE", "resume": "RESUME", "resume controls": "RESUME",
    }
    if value in exact:
        return "simple", exact[value], {}
    if not value or value in {"blah blah", "gibberish", "asdf"}:
        return "rejected", None, {}
    if value in {"go next", "move", "do it", "stop", "scroll", "next"}:
        return "ambiguous", None, {}
    complex_markers = ("temperature", "motor", "machine", "fault", "overheat", "guide", "report", "troubleshoot")
    if any(word in value for word in complex_markers):
        return "complex", None, {}
    return "rejected", None, {}


class MockExecutor:
    """A local stand-in for the extension; records executions for dedup checks."""

    def __init__(self) -> None:
        self.executed: list[Action] = []

    def execute(self, action: Action) -> ActionResult:
        self.executed.append(action)
        return ActionResult("ACTION_RESULT", action.request_id, True, f"Mock executed {action.action}")


class ActionRouter:
    def __init__(self, executor: MockExecutor | None = None, intent_pipeline: Any | None = None,
                 resolver: Any | None = None, confirmation_seconds: float = 8.0,
                 session_logger: Any | None = None) -> None:
        self.executor = executor or MockExecutor()
        self.intent_pipeline = intent_pipeline
        self.resolver = resolver or getattr(intent_pipeline, "resolver", None)
        self.confirmation_seconds = confirmation_seconds
        self.session_logger = session_logger
        self.last_pipeline_details: dict[str, Any] = {}
        self.pending_confirmation: dict[str, Any] | None = None
        self.paused = False
        self.results: dict[str, ActionResult] = {}

    def handle_text(self, text: str, profile: str, site_type: str, request_id: str | None = None) -> dict[str, Any]:
        self.last_pipeline_details = {}
        result = self._handle_text(text, profile, site_type, request_id)
        if self.session_logger:
            self.session_logger.write({
                "transcript": text,
                "site_type": site_type,
                "profile": profile,
                "templated_text": self.last_pipeline_details.get("templated_text"),
                "matcher": self.last_pipeline_details.get("match"),
                "escalation_trigger": self.last_pipeline_details.get("trigger"),
                "gemini_candidates": self.last_pipeline_details.get("candidates", []),
                "final_result": result,
            })
        return result

    def _handle_text(self, text: str, profile: str, site_type: str, request_id: str | None = None) -> dict[str, Any]:
        normalized = normalize(text)
        if self.pending_confirmation:
            pending = self.pending_confirmation
            if time.monotonic() > pending["expires_at"]:
                self.pending_confirmation = None
                if normalized in {"yes", "confirm", "confirm it"}:
                    return asdict(ActionResult("ACTION_RESULT", pending["request_id"], False,
                                               "The proposed action expired", "CONFIRMATION_EXPIRED"))
            elif normalized in {"yes", "confirm", "confirm it"}:
                self.pending_confirmation = None
                params = dict(pending["parameters"])
                if ACTION_RULES[pending["action"]]["consequential"]:
                    params["approved"] = True
                return self.dispatch(Action("ACTION", "VOICE", pending["action"], profile, params,
                                            pending["request_id"]), site_type)
            elif normalized in {"no", "cancel", "never mind", "nevermind"}:
                self.pending_confirmation = None
                return asdict(ActionResult("ACTION_RESULT", pending["request_id"], False,
                                           "Proposed action cancelled", "CANCELLED"))
            else:
                # Any new utterance cancels the pending proposal before it is
                # parsed, so a stale confirmation can never fire later.
                self.pending_confirmation = None

        if normalized in {"yes", "confirm", "confirm it"}:
            return asdict(ActionResult("ACTION_RESULT", request_id or str(uuid4()), False,
                                       "There is no pending action to confirm", "UNRECOGNIZED"))
        kind, action_name, parameters = parse_intent(text)
        fast_actions = {"SCROLL_UP", "SCROLL_DOWN", "NEXT_PANEL", "PREVIOUS_PANEL",
                        "NEXT_SECTION", "PREVIOUS_SECTION", "PAUSE", "RESUME"}
        # Resolve deterministic KiCad commands from the whole transcript first.
        # This safely dispatches known targets without AI and catches
        # contradictory descriptors (for example, "J108 USB connector").
        kicad_actions = {
            name for name, rule in ACTION_RULES.items()
            if "KICAD_SCHEMATIC" in rule["sites"] and name not in fast_actions
        }
        if kind == "simple" and action_name in kicad_actions and self.resolver:
            from resolver import parameters_for_action

            resolved_parameters, resolution_error = parameters_for_action(action_name, text, self.resolver)
            if resolution_error or resolved_parameters is None:
                reason = resolution_error or "UNRESOLVED_ENTITY"
                if reason in {"UNKNOWN_TARGET", "AMBIGUOUS"}:
                    message = ("Command refers to an unknown target" if reason == "UNKNOWN_TARGET"
                               else "Command target is ambiguous")
                    return asdict(ActionResult("ACTION_RESULT", request_id or str(uuid4()), False,
                                               message, reason))
                # The action pattern may be clear even if this phrase for the
                # target is unfamiliar. Let semantic matching try before giving up.
            else:
                self.last_pipeline_details = {"source": "REGEX", "parsed_action": action_name}
                return self.dispatch(Action("ACTION", "VOICE", action_name, profile,
                                            resolved_parameters, request_id or str(uuid4())), site_type)
        # A missing regex match leaves action_name as None, which deliberately
        # falls through to the semantic pipeline instead of being rejected here.
        if self.intent_pipeline is not None and action_name not in fast_actions:
            decision = self.intent_pipeline.decide(text, profile, site_type)
            self.last_pipeline_details = dict(decision.details or {})
            self.last_pipeline_details.update({
                "trigger": decision.trigger,
                "candidates": list(decision.candidates),
                "status": decision.status,
            })
            if decision.status == "ACCEPTED" and decision.action:
                return self.dispatch(Action("ACTION", "VOICE", decision.action,
                                            profile, decision.parameters or {}, request_id or str(uuid4())), site_type)
            if decision.status == "CONFIRM" and decision.action:
                req_id = request_id or str(uuid4())
                self.pending_confirmation = {
                    "action": decision.action,
                    "parameters": decision.parameters or {},
                    "request_id": req_id,
                    "expires_at": time.monotonic() + self.confirmation_seconds,
                }
                return {"type": "ACTION_RESULT", "request_id": req_id, "success": False,
                        "message": f"Please confirm: {decision.action}", "reason": "CONFIRMATION_REQUIRED",
                        "proposal": {"action": decision.action, "parameters": decision.parameters or {},
                                     "candidates": list(decision.candidates), "trigger": decision.trigger}}
            return {"type": "ACTION_RESULT", "request_id": request_id or str(uuid4()), "success": False,
                    "message": decision.details.get("reason", decision.status) if decision.details else decision.status,
                    "reason": decision.status, "details": decision.details or {}}
        if kind == "complex":
            return {"type": "VOICE_EVENT", "text": text, "status": "FORWARDED_TO_PLANNER"}
        if kind != "simple":
            return asdict(ActionResult("ACTION_RESULT", request_id or str(uuid4()), False,
                                       "Command was not clear enough to execute", kind.upper()))
        return self.dispatch(Action("ACTION", "VOICE", action_name or "", profile, parameters, request_id or str(uuid4())), site_type)

    def dispatch(self, action: Action, site_type: str) -> dict[str, Any]:
        if action.request_id in self.results:
            return asdict(self.results[action.request_id])
        result: ActionResult
        rule = ACTION_RULES.get(action.action)
        if not rule:
            result = ActionResult("ACTION_RESULT", action.request_id, False, "Action is not allowed", "INVALID_ACTION")
        elif set(action.parameters) != set(rule["parameters"]) or any(
            not isinstance(action.parameters.get(k), typ) or (typ is int and isinstance(action.parameters.get(k), bool))
            for k, typ in rule["parameters"].items()
        ):
            result = ActionResult("ACTION_RESULT", action.request_id, False, "Action arguments are invalid", "INVALID_ARGS")
        elif action.profile not in rule["profiles"] or site_type not in rule["sites"]:
            result = ActionResult("ACTION_RESULT", action.request_id, False, "Action is not supported in this profile or website", "UNSUPPORTED_PAGE")
        elif self.paused and action.action != "RESUME":
            result = ActionResult("ACTION_RESULT", action.request_id, False, "Controls are paused", "PAUSED")
        elif self.resolver and (resolution := self._validate_resolved_arguments(action)) is not None:
            result = ActionResult("ACTION_RESULT", action.request_id, False,
                                  "Action target is not a resolved KiCad entity", resolution)
        elif rule["consequential"] and action.parameters.get("approved") is not True:
            result = ActionResult("ACTION_RESULT", action.request_id, False, "User approval is required", "APPROVAL_REQUIRED")
        elif action.action == "PAUSE":
            self.paused = True
            self.pending_confirmation = None
            result = ActionResult("ACTION_RESULT", action.request_id, True, "Controls paused")
        elif action.action == "RESUME":
            self.paused = False
            result = ActionResult("ACTION_RESULT", action.request_id, True, "Controls resumed")
        else:
            result = self.executor.execute(action)
        self.results[action.request_id] = result
        return asdict(result)

    def _validate_resolved_arguments(self, action: Action) -> str | None:
        requirements = {
            "LOCATE_COMPONENT": ("component_ref", "component"),
            "EXPLAIN_COMPONENT": ("component_ref", "component"),
            "MARK_COMPONENT_COMPLETE": ("component_ref", "component"),
            "TRACE_SIGNAL": ("signal_name", "signal"),
            "OPEN_SHEET": ("sheet_id", "sheet"),
            "SHOW_ASSEMBLY_CHECKLIST": ("section_id", "section"),
            "SHOW_SCHEMATIC_SECTION": ("section_id", "section"),
            "GUIDE_TROUBLESHOOTING": ("issue", "issue"),
        }
        requirement = requirements.get(action.action)
        if not requirement:
            return None
        parameter, entity_type = requirement
        value = action.parameters.get(parameter)
        if not isinstance(value, str):
            return "INVALID_ARGS"
        values = [part.strip() for part in value.split(",")] if entity_type == "signal" else [value]
        resolved = []
        for item in values:
            target = self.resolver.resolve(item, entity_type)
            if target.status != "RESOLVED":
                return "UNKNOWN_TARGET" if target.status == "UNKNOWN_TARGET" else "AMBIGUOUS" if target.status == "AMBIGUOUS" else "UNKNOWN_TARGET"
            if entity_type == "signal":
                entity = next(entry for entry in self.resolver.collections[entity_type] if entry["id"] == target.canonical)
                resolved.append(entity.get("canonical", target.canonical))
            else:
                resolved.append(target.canonical)
        if entity_type == "signal" and ", ".join(resolved) != value:
            return "INVALID_ARGS"
        if entity_type != "signal" and resolved[0] != value:
            return "INVALID_ARGS"
        return None
