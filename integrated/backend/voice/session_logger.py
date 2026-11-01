"""Append safe per-utterance pipeline diagnostics as JSON Lines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SessionLogger:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path(__file__).parent / "data" / "logs" / "utterances.jsonl"

    def write(self, entry: dict[str, Any]) -> None:
        # Callers pass only transcripts, matcher decisions, candidate summaries,
        # and action results; credentials and prompts are deliberately excluded.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
