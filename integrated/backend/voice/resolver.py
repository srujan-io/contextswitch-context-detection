"""Ground-truth entity resolution for the KiCad command pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import json
from pathlib import Path
import re
from typing import Any


REFERENCE_RE = re.compile(r"(?<![a-z0-9])(?:tee\s+pee|jay|see|are|t\s*p|tp|[jcr])\s*[-_ ]*\s*(?:\d{2,4}[a-z]?|(?:one|two|three|four|five|six|seven|eight|nine|zero|oh)(?:\s+(?:one|two|three|four|five|six|seven|eight|nine|zero|oh)){1,3})(?![a-z0-9])", re.I)
NUMBER_WORDS = {"zero":"0", "oh":"0", "one":"1", "two":"2", "three":"3", "four":"4", "five":"5", "six":"6", "seven":"7", "eight":"8", "nine":"9"}
PREFIX_WORDS = {"jay":"J", "see":"C", "are":"R", "tee pee":"TP"}
STOPWORDS = {"the", "a", "an", "component", "connector", "sheet", "schematic", "section", "area", "part", "net", "signal", "connections", "connection"}


def normalize_text(text: str) -> str:
    value = text.lower().replace("’", "'").replace("−", "-").replace("–", "-")
    value = re.sub(r"[^a-z0-9_' +.-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def canonical_component_ref(raw: str) -> str | None:
    value = normalize_text(raw).strip().replace("-", " ").replace("_", " ")
    value = re.sub(r"\s+", " ", value)
    prefix = None
    for spoken, letter in PREFIX_WORDS.items():
        if value == spoken or value.startswith(spoken + " "):
            prefix, value = letter, value[len(spoken):].strip()
            break
    if prefix is None:
        match = re.match(r"^(tp|[jcr])\s*(.*)$", value)
        if not match:
            return None
        prefix, value = match.group(1).upper(), match.group(2).strip()
    if re.fullmatch(r"\d{2,4}[a-z]?", value, re.I):
        return prefix + re.sub(r"\s+", "", value).upper()
    digits = value.split()
    if digits and all(part in NUMBER_WORDS for part in digits):
        number = "".join(NUMBER_WORDS[part] for part in digits)
        if 2 <= len(number) <= 4:
            return prefix + number
    return None


@dataclass(frozen=True)
class Resolution:
    status: str
    entity_type: str
    canonical: str | None = None
    candidates: tuple[str, ...] = ()
    matched_text: str | None = None


class GroundTruthResolver:
    def __init__(self, ground_truth: dict[str, Any] | str | Path, fuzzy_threshold: float = 0.92):
        if isinstance(ground_truth, (str, Path)):
            ground_truth = json.loads(Path(ground_truth).read_text())
        self.data = ground_truth
        self.fuzzy_threshold = fuzzy_threshold
        self.collections = {
            "component": ground_truth.get("components", []),
            "signal": ground_truth.get("signals", []),
            "sheet": ground_truth.get("sheets", []),
            "section": ground_truth.get("sections", []),
            "issue": ground_truth.get("issues", []),
        }

    @classmethod
    def from_default_file(cls) -> "GroundTruthResolver":
        return cls(Path(__file__).parent / "data" / "kicad_ground_truth.json")

    def resolve(self, raw: str, entity_type: str) -> Resolution:
        entities = self.collections.get(entity_type, [])
        if entity_type == "component":
            refs = [canonical_component_ref(item.group(0)) for item in REFERENCE_RE.finditer(raw)]
            refs = [item for item in refs if item]
            known = {entity["id"] for entity in entities}
            if refs:
                unique = tuple(dict.fromkeys(refs))
                unknown = [ref for ref in unique if ref not in known]
                if unknown:
                    return Resolution("UNKNOWN_TARGET", entity_type, candidates=tuple(unknown), matched_text=unknown[0])
                if len(unique) > 1:
                    return Resolution("AMBIGUOUS", entity_type, candidates=unique)
                reference = unique[0]
                contradiction = self._component_descriptor_conflict(raw, reference, entities)
                if contradiction:
                    return Resolution("AMBIGUOUS", entity_type, candidates=(reference, contradiction), matched_text=raw)
                return Resolution("RESOLVED", entity_type, reference, matched_text=REFERENCE_RE.search(raw).group(0))

        normalized = normalize_text(raw)
        exact_hits: list[tuple[int, str, str]] = []
        for entity in entities:
            aliases = [entity.get("id", ""), entity.get("canonical", ""), entity.get("description", "")]
            aliases += entity.get("synonyms", [])
            for alias in filter(None, aliases):
                alias_norm = normalize_text(alias)
                if alias_norm and _contains_phrase(normalized, alias_norm):
                    exact_hits.append((len(alias_norm), entity.get("id", ""), alias))
        if exact_hits:
            longest = max(hit[0] for hit in exact_hits)
            ids = tuple(dict.fromkeys(hit[1] for hit in exact_hits if hit[0] == longest))
            if len(ids) > 1:
                return Resolution("AMBIGUOUS", entity_type, candidates=ids, matched_text=raw)
            target_id = ids[0]
            alias = next(hit[2] for hit in exact_hits if hit[1] == target_id and hit[0] == longest)
            return Resolution("RESOLVED", entity_type, target_id, matched_text=alias)

        # Fuzzy matching is only applied to short entity-like inputs, never an
        # entire command sentence, so unrelated prose cannot become a target.
        words = [word for word in re.findall(r"[a-z0-9]+", normalized) if word not in STOPWORDS]
        query = " ".join(words)
        if query:
            scored: list[tuple[float, str, str]] = []
            for entity in entities:
                for alias in [entity.get("id", ""), *entity.get("synonyms", [])]:
                    alias_norm = " ".join(word for word in re.findall(r"[a-z0-9]+", normalize_text(alias)) if word not in STOPWORDS)
                    if alias_norm:
                        score = difflib.SequenceMatcher(None, query, alias_norm).ratio()
                        if score >= self.fuzzy_threshold:
                            scored.append((score, entity["id"], alias))
            if scored:
                best = max(item[0] for item in scored)
                ids = tuple(dict.fromkeys(item[1] for item in scored if item[0] == best))
                if len(ids) != 1:
                    return Resolution("AMBIGUOUS", entity_type, candidates=ids, matched_text=raw)
                alias = next(item[2] for item in scored if item[0] == best and item[1] == ids[0])
                return Resolution("RESOLVED", entity_type, ids[0], matched_text=alias)
        return Resolution("NO_MATCH", entity_type)

    def targets_in_text(self, text: str) -> dict[str, Resolution]:
        results = {kind: self.resolve(text, kind) for kind in self.collections}
        return results

    def template(self, text: str, entities: dict[str, Resolution] | None = None) -> str:
        entities = entities or self.targets_in_text(text)
        result = normalize_text(text)
        # Replace component references first, so spoken spacing variants are
        # templated consistently even when the target alias was not literal.
        result = REFERENCE_RE.sub(" <COMPONENT> ", result)
        for kind, placeholder in (("component", "COMPONENT"), ("signal", "SIGNAL"),
                                  ("sheet", "SHEET"), ("section", "SECTION"), ("issue", "ISSUE")):
            resolution = entities.get(kind)
            if resolution and resolution.status == "RESOLVED" and resolution.matched_text:
                alias = normalize_text(resolution.matched_text)
                if alias and alias not in {resolution.canonical.lower()}:
                    result = re.sub(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", f" <{placeholder}> ", result)
        return re.sub(r"\s+", " ", result).strip()

    def _component_descriptor_conflict(self, raw: str, reference: str, entities: list[dict[str, Any]]) -> str | None:
        ref_match = REFERENCE_RE.search(raw)
        remainder = raw[:ref_match.start()] + " " + raw[ref_match.end():] if ref_match else raw
        remainder_norm = normalize_text(remainder)
        known_descriptors: list[str] = []
        for entity in entities:
            if entity["id"] == reference:
                continue
            for alias in filter(None, [entity.get("description", ""), *entity.get("synonyms", [])]):
                alias_norm = normalize_text(alias)
                if alias_norm and _contains_phrase(remainder_norm, alias_norm):
                    known_descriptors.append(entity["id"])
        if known_descriptors:
            return known_descriptors[0]
        return None


def _contains_phrase(text: str, phrase: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))


def parameters_for_action(action: str, text: str, resolver: GroundTruthResolver) -> tuple[dict[str, str] | None, str | None]:
    requirements = {
        "LOCATE_COMPONENT": ("component", "component_ref"),
        "EXPLAIN_COMPONENT": ("component", "component_ref"),
        "MARK_COMPONENT_COMPLETE": ("component", "component_ref"),
        "TRACE_SIGNAL": ("signal", "signal_name"),
        "OPEN_SHEET": ("sheet", "sheet_id"),
        "SHOW_ASSEMBLY_CHECKLIST": ("section", "section_id"),
        "SHOW_SCHEMATIC_SECTION": ("section", "section_id"),
        "GUIDE_TROUBLESHOOTING": ("issue", "issue"),
    }
    required = requirements.get(action)
    if not required:
        return {}, None
    kind, parameter = required
    resolution = resolver.resolve(text, kind)
    if resolution.status != "RESOLVED":
        reason = "UNKNOWN_TARGET" if resolution.status == "UNKNOWN_TARGET" else "AMBIGUOUS" if resolution.status == "AMBIGUOUS" else "UNRESOLVED_ENTITY"
        return None, reason
    if kind == "signal":
        target = next(item for item in resolver.collections[kind] if item["id"] == resolution.canonical)
        value = target.get("canonical", resolution.canonical)
    else:
        value = resolution.canonical
    return {parameter: value}, None
