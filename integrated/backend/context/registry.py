import json
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent / "skill_packs"


def load_skill_pack(website_id: str) -> dict:
    filename = f"{website_id}.json" if website_id in {"kicanvas", "youtube"} else "default.json"
    path = SKILL_DIR / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"website_id": website_id, "capabilities": []}
