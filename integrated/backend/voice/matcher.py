"""Embedding-backed intent ranking with explicit calibration gates."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Protocol


class SentenceEncoder(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEncoder:
    """Local sentence encoder; the model downloads once and is then local."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise RuntimeError("fastembed is unavailable; install member3/requirements.txt") from exc
        self.model = TextEmbedding(model_name=model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, vector)) for vector in self.model.embed(texts)]


@dataclass(frozen=True)
class RankedAction:
    action: str
    score: float


@dataclass(frozen=True)
class MatchResult:
    accepted: bool
    top_action: str | None
    top_score: float | None
    second_action: str | None
    second_score: float | None
    trigger: str | None
    ranked: tuple[RankedAction, ...] = ()


class EmbeddingMatcher:
    def __init__(self, catalog: dict[str, Any], encoder: SentenceEncoder,
                 threshold: float | None = None, margin: float | None = None,
                 calibrated: bool | None = None):
        self.catalog = catalog
        self.encoder = encoder
        self.threshold = threshold
        self.margin = margin
        self.calibrated = (threshold is not None and margin is not None) if calibrated is None else calibrated
        self._examples: dict[str, list[list[float]]] = {}
        self._primed = False

    def prime(self) -> None:
        actions = self.catalog.get("actions", [])
        all_examples = [(action["action"], phrase) for action in actions for phrase in action.get("examples", [])]
        vectors = self.encoder.encode([phrase for _, phrase in all_examples])
        if len(vectors) != len(all_examples):
            raise ValueError("Encoder returned the wrong number of vectors")
        self._examples = {action["action"]: [] for action in actions}
        for (action, _), vector in zip(all_examples, vectors):
            self._examples[action].append(vector)
        self._primed = True

    def match(self, templated_text: str, unresolved_entity: bool = False) -> MatchResult:
        if unresolved_entity:
            return MatchResult(False, None, None, None, None, "UNRESOLVED_ENTITY")
        if _possibly_clipped(templated_text):
            return MatchResult(False, None, None, None, None, "POSSIBLY_CLIPPED")
        try:
            if not self._primed:
                self.prime()
            query = self.encoder.encode([templated_text])[0]
        except Exception:
            return MatchResult(False, None, None, None, None, "EMBEDDER_UNAVAILABLE")
        ranked = []
        for action, vectors in self._examples.items():
            if vectors:
                ranked.append(RankedAction(action, max(_cosine(query, candidate) for candidate in vectors)))
        ranked.sort(key=lambda item: item.score, reverse=True)
        if not ranked:
            return MatchResult(False, None, None, None, None, "LOW_SCORE")
        top = ranked[0]
        second = ranked[1] if len(ranked) > 1 else None
        if not self.calibrated or self.threshold is None or self.margin is None:
            trigger = "UNCALIBRATED"
        elif top.score < self.threshold:
            trigger = "LOW_SCORE"
        elif second and top.score - second.score < self.margin:
            trigger = "THIN_MARGIN"
        else:
            trigger = None
        return MatchResult(
            trigger is None,
            top.action,
            top.score,
            second.action if second else None,
            second.score if second else None,
            trigger,
            tuple(ranked),
        )


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions differ")
    numerator = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if not norm_left or not norm_right:
        return 0.0
    return numerator / (norm_left * norm_right)


def _possibly_clipped(text: str) -> bool:
    words = text.split()
    if len(words) < 2:
        return True
    clipped = ("conne", "regul", "microcon", "schem", "assemb", "communi")
    return any(words[-1].endswith(fragment) for fragment in clipped)
