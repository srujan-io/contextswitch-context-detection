"""Grounded Gemini candidate generation. This module never executes actions."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from resolver import GroundTruthResolver, normalize_text, parameters_for_action


@dataclass(frozen=True)
class Interpretation:
    status: str
    candidates: tuple[dict[str, Any], ...] = ()
    ambiguous: bool = False
    error_code: str | None = None


class GeminiInterpreter:
    def __init__(self, client: Any, model: str, catalog: dict[str, Any], resolver: GroundTruthResolver):
        self.client = client
        self.model = model
        self.catalog = catalog
        self.resolver = resolver
        self._cache: dict[tuple[str, str, str], Interpretation] = {}
        self.actions = {entry["action"]: entry for entry in catalog.get("actions", [])}

    def interpret(self, transcript: str, site_type: str, profile: str, trigger: str) -> Interpretation:
        key = (normalize_text(transcript), site_type, profile)
        if key in self._cache:
            return self._cache[key]
        if site_type != self.catalog.get("site_type"):
            return Interpretation("UNRECOGNIZED", error_code="UNSUPPORTED_PAGE")
        component_resolution = self.resolver.resolve(transcript, "component")
        if component_resolution.status == "AMBIGUOUS":
            return Interpretation("AMBIGUOUS", ambiguous=True, error_code="AMBIGUOUS")
        if component_resolution.status == "UNKNOWN_TARGET":
            return Interpretation("UNRECOGNIZED", error_code="UNKNOWN_TARGET")
        targets = _known_target_summary(self.resolver)
        action_entries = [entry for entry in self.catalog.get("actions", [])]
        prompt = _build_prompt(transcript, site_type, profile, trigger, action_entries, targets)
        schema = _response_schema(list(self.actions))
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "temperature": 0,
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )
        except Exception:
            # The shared SDK client is configured for at most one network retry.
            result = Interpretation("UNAVAILABLE", error_code="GEMINI_FAILURE")
            self._cache[key] = result
            return result
        try:
            response_text = getattr(response, "text", None)
            payload = json.loads(response_text if isinstance(response_text, str) else "{}")
        except (TypeError, AttributeError, json.JSONDecodeError):
            result = Interpretation("UNAVAILABLE", error_code="INVALID_MODEL_JSON")
            self._cache[key] = result
            return result
        if payload.get("ambiguous") is True:
            result = Interpretation("AMBIGUOUS", ambiguous=True, error_code="AMBIGUOUS")
            self._cache[key] = result
            return result
        raw_candidates = payload.get("candidates", [])
        if not isinstance(raw_candidates, list):
            result = Interpretation("UNRECOGNIZED", error_code="UNRECOGNIZED")
            self._cache[key] = result
            return result
        accepted = []
        for raw in raw_candidates[:3]:
            candidate = self._validate_candidate(raw, transcript)
            if candidate:
                accepted.append(candidate)
        result = Interpretation("CANDIDATES" if accepted else "UNRECOGNIZED", tuple(accepted), error_code=None if accepted else "UNRECOGNIZED")
        self._cache[key] = result
        return result

    def _validate_candidate(self, raw: Any, transcript: str) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        action = raw.get("action")
        if action not in self.actions:
            return None
        evidence = raw.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip() or not _is_grounded(evidence, transcript):
            return None
        params = raw.get("params", {})
        if not isinstance(params, dict):
            return None
        allowed = set(self.actions[action].get("parameters", []))
        if set(params) - allowed:
            return None
        resolved, reason = parameters_for_action(action, transcript, self.resolver)
        if reason or resolved is None:
            return None
        # Model output cannot introduce or change target values. It may omit
        # extracted parameters; code supplies only resolver-grounded values.
        for name, value in params.items():
            expected = resolved.get(name)
            if expected is None or not _same_target(value, expected, name, self.resolver):
                return None
        required = set(self.actions[action].get("parameters", []))
        if set(resolved) != required:
            return None
        return {"action": action, "params": resolved, "evidence": evidence}


def _is_grounded(evidence: str, transcript: str) -> bool:
    evidence_norm = normalize_text(evidence)
    transcript_norm = normalize_text(transcript)
    return bool(evidence_norm and evidence_norm in transcript_norm)


def _same_target(value: Any, expected: str, parameter: str, resolver: GroundTruthResolver) -> bool:
    if not isinstance(value, str):
        return False
    if normalize_text(value) == normalize_text(expected):
        return True
    entity_type = {
        "component_ref": "component", "signal_name": "signal", "sheet_id": "sheet",
        "section_id": "section", "issue": "issue",
    }.get(parameter)
    if entity_type:
        resolution = resolver.resolve(value, entity_type)
        return resolution.status == "RESOLVED" and resolution.canonical == expected
    return False


def _known_target_summary(resolver: GroundTruthResolver) -> dict[str, list[str]]:
    return {kind: [entry["id"] for entry in entries] for kind, entries in resolver.collections.items()}


def _build_prompt(transcript: str, site: str, profile: str, trigger: str,
                  actions: list[dict[str, Any]], known_targets: dict[str, list[str]]) -> str:
    return (
        "Interpret this voice command for a supported KiCad schematic viewer. "
        "Return JSON with keys ambiguous and candidates. Candidates contain at most three objects "
        "with action, params, and evidence. Choose actions only from the supplied catalog. "
        "Extract target values only from the transcript; never invent or repair a contradictory target. "
        "If no action clearly fits, return no candidates. This is a candidate proposal only; it will not execute here.\n"
        f"Site: {site}\nProfile: {profile}\nEscalation trigger: {trigger}\n"
        f"Transcript: {transcript}\nKnown targets: {json.dumps(known_targets, sort_keys=True)}\n"
        f"Active catalog: {json.dumps(actions, sort_keys=True)}"
    )


def _response_schema(actions: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "ambiguous": {"type": "boolean"},
            "candidates": {"type": "array", "maxItems": 3, "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": actions},
                    "params": {"type": "object", "additionalProperties": {"type": "string"}},
                    "evidence": {"type": "string"},
                },
                "required": ["action", "params", "evidence"],
            }},
        },
        "required": ["ambiguous", "candidates"],
    }
