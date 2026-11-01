"""Resolver -> embedding ranker -> Gemini candidate escalation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from interpreter import GeminiInterpreter, Interpretation
from matcher import EmbeddingMatcher, FastEmbedEncoder, MatchResult
from resolver import GroundTruthResolver, normalize_text, parameters_for_action
from settings import create_gemini_client, load_settings


@dataclass(frozen=True)
class PipelineDecision:
    status: str
    action: str | None = None
    parameters: dict[str, str] | None = None
    trigger: str | None = None
    candidates: tuple[dict[str, Any], ...] = ()
    details: dict[str, Any] | None = None


class _UnavailableEncoder:
    def encode(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Local embedding model is unavailable")


class _UnavailableInterpreter:
    def interpret(self, transcript: str, site_type: str, profile: str, trigger: str) -> Interpretation:
        return Interpretation("UNAVAILABLE", error_code="GEMINI_UNAVAILABLE")


class IntentPipeline:
    def __init__(self, resolver: GroundTruthResolver, matcher: EmbeddingMatcher,
                 interpreter: GeminiInterpreter | Any, site_type: str = "KICAD_SCHEMATIC"):
        self.resolver = resolver
        self.matcher = matcher
        self.interpreter = interpreter
        self.site_type = site_type

    def decide(self, transcript: str, profile: str, site_type: str) -> PipelineDecision:
        if site_type != self.site_type or profile != "PCB_WEB":
            return PipelineDecision("UNSUPPORTED_PAGE", details={"reason": "Action unavailable in active context"})
        targets = self.resolver.targets_in_text(transcript)
        for kind in ("component", "signal", "sheet", "section", "issue"):
            target = targets[kind]
            if target.status == "AMBIGUOUS":
                return PipelineDecision("AMBIGUOUS", details={"entity_type": kind, "candidates": target.candidates})
            if target.status == "UNKNOWN_TARGET":
                return PipelineDecision("UNKNOWN_TARGET", details={"entity_type": kind, "candidates": target.candidates})
        templated = self.resolver.template(transcript, targets)
        match = self.matcher.match(templated)
        if match.accepted and match.top_action:
            parameters, error = parameters_for_action(match.top_action, transcript, self.resolver)
            if error or parameters is None:
                return PipelineDecision(error or "UNRESOLVED_ENTITY", trigger=match.trigger,
                                        details={"templated_text": templated, "match": _match_json(match)})
            return PipelineDecision("ACCEPTED", match.top_action, parameters, details={
                "templated_text": templated, "match": _match_json(match), "source": "EMBEDDING"})

        trigger = match.trigger or "LOW_SCORE"
        interpretation = self.interpreter.interpret(transcript, site_type, profile, trigger)
        if interpretation.status == "AMBIGUOUS":
            return PipelineDecision("AMBIGUOUS", trigger=trigger, details={"reason": interpretation.error_code})
        if interpretation.status != "CANDIDATES" or not interpretation.candidates:
            return PipelineDecision(interpretation.error_code or interpretation.status, trigger=trigger,
                                    details={"templated_text": templated, "match": _match_json(match)})
        candidate = interpretation.candidates[0]
        return PipelineDecision("CONFIRM", candidate["action"], candidate["params"], trigger,
                                interpretation.candidates,
                                {"templated_text": templated, "match": _match_json(match), "source": "GEMINI"})


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else Path(__file__).parent / "data" / "catalogs" / "kicad.json"
    return json.loads(path.read_text())


def build_default_pipeline() -> IntentPipeline:
    root = Path(__file__).parent
    catalog = load_catalog()
    resolver = GroundTruthResolver(root / "data" / "kicad_ground_truth.json")
    config = json.loads((root / "data" / "config" / "kicad_matcher.json").read_text())
    settings = load_settings()
    try:
        encoder = FastEmbedEncoder(config.get("embedding_model", settings.embedding_model))
    except Exception:
        encoder = _UnavailableEncoder()
    matcher = EmbeddingMatcher(catalog, encoder, config.get("threshold"), config.get("margin"),
                               calibrated=config.get("calibrated", False))
    try:
        interpreter = GeminiInterpreter(create_gemini_client(settings), settings.model, catalog, resolver)
    except Exception:
        interpreter = _UnavailableInterpreter()
    return IntentPipeline(resolver, matcher, interpreter, catalog["site_type"])


def _match_json(match: MatchResult) -> dict[str, Any]:
    return {
        "top_action": match.top_action,
        "top_score": match.top_score,
        "second_action": match.second_action,
        "second_score": match.second_score,
        "trigger": match.trigger,
    }
