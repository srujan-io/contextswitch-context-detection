"""Score labeled KiCad utterances and report zero-false-accept thresholds.

This script does not write a threshold automatically. Review the printed
coverage and error counts, then record a selected pair in data/config only if
the held-out set has zero wrong accepts.
"""

from __future__ import annotations

import json
from pathlib import Path

from matcher import EmbeddingMatcher, FastEmbedEncoder
from pipeline import load_catalog
from resolver import GroundTruthResolver
from settings import load_settings


ROOT = Path(__file__).parent


def main() -> int:
    config = json.loads((ROOT / "data" / "config" / "kicad_matcher.json").read_text())
    labels = json.loads((ROOT / "data" / "labeled_phrases.json").read_text())["phrases"]
    resolver = GroundTruthResolver(ROOT / "data" / "kicad_ground_truth.json")
    settings = load_settings()
    encoder = FastEmbedEncoder(config.get("embedding_model", settings.embedding_model))
    matcher = EmbeddingMatcher(load_catalog(), encoder)
    records = []
    for item in labels:
        targets = resolver.targets_in_text(item["text"])
        templated = resolver.template(item["text"], targets)
        result = matcher.match(templated)
        ranked = result.ranked
        top = ranked[0] if ranked else None
        second = ranked[1] if len(ranked) > 1 else None
        records.append({
            "text": item["text"],
            "expected": item["expected_action"],
            "top_action": top.action if top else None,
            "top_score": top.score if top else 0.0,
            "margin": top.score - second.score if top and second else 0.0,
            "templated": templated,
        })

    positive = [row for row in records if row["expected"] is not None]
    negative = [row for row in records if row["expected"] is None]
    correct_scores = [row["top_score"] for row in positive if row["top_action"] == row["expected"]]
    wrong_scores = [row["top_score"] for row in records if row["top_action"] != row["expected"]]
    print(json.dumps({
        "phrase_count": len(records),
        "positive_count": len(positive),
        "negative_count": len(negative),
        "correct_top_score_range": _range(correct_scores),
        "wrong_top_score_range": _range(wrong_scores),
        "rows": records,
    }, indent=2))
    print("\nCandidate thresholds with zero wrong accepts:")
    choices = _zero_wrong_thresholds(records)
    if not choices:
        print("None found; improve labels/examples or keep embeddings uncalibrated.")
    else:
        for choice in choices[:5]:
            print(json.dumps(choice))
    return 0


def _range(values: list[float]) -> dict[str, float] | None:
    return {"min": min(values), "max": max(values)} if values else None


def _zero_wrong_thresholds(records: list[dict]) -> list[dict]:
    scores = sorted({0.0, 1.01, *(row["top_score"] for row in records)})
    margins = sorted({0.0, 1.01, *(row["margin"] for row in records)})
    choices = []
    for threshold in scores:
        for margin in margins:
            accepted = [row for row in records if row["top_score"] >= threshold and row["margin"] >= margin]
            errors = [row for row in accepted if row["expected"] != row["top_action"]]
            true_positives = [row for row in accepted if row["expected"] == row["top_action"]]
            if not errors:
                choices.append({"threshold": threshold, "margin": margin,
                                "accepted_correct": len(true_positives), "accepted_total": len(accepted),
                                "wrong_accepts": 0})
    choices.sort(key=lambda row: (row["accepted_correct"], row["threshold"], row["margin"]), reverse=True)
    return choices


if __name__ == "__main__":
    raise SystemExit(main())
