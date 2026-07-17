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


_tag_cache: dict[str, list[dict]] | None = None


def invalidate_tag_cache():
    global _tag_cache
    _tag_cache = None


def load_tags() -> dict[str, list[dict]]:
    global _tag_cache
    if _tag_cache is not None:
        return _tag_cache
    if not os.path.exists(TAGS_FILE):
        _tag_cache = {}
        return {}
    try:
        with open(TAGS_FILE, "r") as f:
            raw = json.load(f)
    except Exception:
        _tag_cache = {}
        return {}
    if not isinstance(raw, dict):
        _tag_cache = {}
        return {}
    _tag_cache = {path: _normalize_entry(val) for path, val in raw.items() if path}
    return _tag_cache


def save_tags(data: dict[str, list[dict]]) -> None:
    global _tag_cache
    os.makedirs(os.path.dirname(TAGS_FILE), exist_ok=True)
    serialized = {path: _serialize_entry(entries) for path, entries in data.items() if path and entries}
    with open(TAGS_FILE, "w") as f:
        json.dump(serialized, f)
    _tag_cache = {path: _normalize_entry(val) for path, val in serialized.items()}
