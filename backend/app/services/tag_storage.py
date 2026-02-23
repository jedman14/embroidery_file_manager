"""
Shared tag storage: path -> list of {name, source} with source "auto" | "manual".
Migration: legacy list-of-strings is normalized to list of {name, source: "manual"} on load.
"""
import json
import os
from typing import Any

TAGS_FILE = os.environ.get("TAGS_FILE", "/app/data/tags.json")

SOURCE_AUTO = "auto"
SOURCE_MANUAL = "manual"


def _normalize_entry(raw: Any) -> list[dict]:
    """Normalize a path's tag list to [{name, source}, ...]. Migrates legacy string list."""
    if not raw or not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append({"name": (item or "").strip(), "source": SOURCE_MANUAL})
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            name = (item.get("name") or "").strip()
            if name:
                result.append({
                    "name": name,
                    "source": item.get("source") if item.get("source") in (SOURCE_AUTO, SOURCE_MANUAL) else SOURCE_MANUAL,
                })
    return result


def _serialize_entry(entries: list[dict]) -> list[dict]:
    """Format for JSON: include source only when 'auto' to keep file small."""
    out = []
    for e in entries:
        name = (e.get("name") or "").strip()
        if not name:
            continue
        src = e.get("source") if e.get("source") in (SOURCE_AUTO, SOURCE_MANUAL) else SOURCE_MANUAL
        out.append({"name": name, "source": src})
    return out


def tag_names(entries: list[dict]) -> list[str]:
    """Extract tag name strings from internal entries."""
    return [e["name"] for e in entries if e.get("name")]


def tag_sources_map(entries: list[dict]) -> dict[str, str]:
    """Build {tagName: "auto"|"manual"} from entries."""
    return {e["name"]: (e.get("source") or SOURCE_MANUAL) for e in entries if e.get("name")}


def load_tags() -> dict[str, list[dict]]:
    """Load tags file and return path -> list of {name, source}. Migrates legacy format."""
    if not os.path.exists(TAGS_FILE):
        return {}
    try:
        with open(TAGS_FILE, "r") as f:
            raw = json.load(f)
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {path: _normalize_entry(val) for path, val in raw.items() if path}


def save_tags(data: dict[str, list[dict]]) -> None:
    """Save path -> list of {name, source} to file."""
    os.makedirs(os.path.dirname(TAGS_FILE), exist_ok=True)
    serialized = {path: _serialize_entry(entries) for path, entries in data.items() if path and entries}
    with open(TAGS_FILE, "w") as f:
        json.dump(serialized, f)
