import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.services.smb_service import SMBService
from app.services.thumbnail_service import ThumbnailService, PREVIEW_SIZE
from app.services.vision_service import suggest_tags_from_image
from app.services.tag_storage import (
    load_tags,
    save_tags,
    tag_names,
    tag_sources_map,
    SOURCE_MANUAL,
)

router = APIRouter()

# Extensions that have renderable thumbnails (for suggest-from-image)
EMBROIDERY_EXTENSIONS = {
    ".dst", ".pes", ".pec", ".exp", ".vp3", ".jef", ".xxx", ".sew",
    ".dsz", ".tap", ".hus", ".pcs", ".ufo", ".emd", ".emb", ".csd", ".10o",
}

def _is_embroidery_file(path: str) -> bool:
    return Path(path).suffix.lower() in EMBROIDERY_EXTENSIONS


_smb = SMBService()
_thumbnail_service = ThumbnailService(_smb)


def _entries_from_string_list(tag_list: List[str]) -> list:
    """Convert API tag string list to internal entries (all manual)."""
    return [{"name": (t or "").strip(), "source": SOURCE_MANUAL} for t in (tag_list or []) if (t or "").strip()]

class TagRequest(BaseModel):
    tags: List[str]

class BatchTagsRequest(BaseModel):
    paths: List[str] = []


class MergeTagsRequest(BaseModel):
    source: str
    target: str


class BulkAddTagRequest(BaseModel):
    tag: str
    paths: List[str] = []

@router.post("/batch")
async def get_tags_batch(request: BatchTagsRequest):
    """Get tags for multiple paths at once. Returns tags (string[]) and tag_sources per path."""
    data = load_tags()
    tags_result = {}
    tag_sources_result = {}
    for path in request.paths:
        entries = data.get(path, [])
        tags_result[path] = tag_names(entries)
        tag_sources_result[path] = tag_sources_map(entries)
    return {"tags": tags_result, "tag_sources": tag_sources_result}

@router.get("")
async def get_tags(path: str = ""):
    """Get tags for a file or folder. Returns tags (string[]) and tag_sources {tagName: auto|manual}."""
    data = load_tags()
    entries = data.get(path, [])
    return {"path": path, "tags": tag_names(entries), "tag_sources": tag_sources_map(entries)}

@router.post("")
async def set_tags(path: str, request: TagRequest):
    """Set tags for a file or folder (all stored as manual)."""
    data = load_tags()
    data[path] = _entries_from_string_list(request.tags)
    save_tags(data)
    names = tag_names(data[path])
    return {"path": path, "tags": names, "tag_sources": tag_sources_map(data[path])}

@router.delete("")
async def remove_tags(path: str):
    """Remove all tags for a file or folder"""
    data = load_tags()
    if path in data:
        del data[path]
        save_tags(data)
    return {"path": path, "tags": [], "tag_sources": {}}

@router.get("/search")
async def search_by_tags(tag: str):
    """Search files by tag. Each result has path, tags (string[]), tag_sources."""
    data = load_tags()
    results = []
    tag_lower = (tag or "").strip().lower()
    for path, entries in data.items():
        names = tag_names(entries)
        if tag_lower in [n.lower() for n in names]:
            results.append({"path": path, "tags": names, "tag_sources": tag_sources_map(entries)})
    return {"results": results}

def _normalize_tag(t: str) -> str:
    return (t or "").strip()


@router.get("/all")
async def get_all_tags(counts: bool = False):
    """Get all unique tags. If counts=True, return list of {name, count}."""
    data = load_tags()
    tag_counts = {}
    for entries in data.values():
        for e in entries:
            n = e.get("name")
            if n:
                tag_counts[n] = tag_counts.get(n, 0) + 1
    if counts:
        return {
            "tags": sorted(
                [{"name": name, "count": c} for name, c in tag_counts.items()],
                key=lambda x: x["name"],
            )
        }
    return {"tags": sorted(list(tag_counts.keys()))}


@router.get("/paths")
async def get_paths_with_tags():
    """Get all paths that have at least one tag (for Create-tag path selector)."""
    tags = load_tags()
    return {"paths": sorted(tags.keys())}


@router.post("/merge")
async def merge_tags(request: MergeTagsRequest):
    """Merge source tag into target: every path with source gets target added and source removed."""
    source = _normalize_tag(request.source)
    target = _normalize_tag(request.target)
    if not source or not target:
        raise HTTPException(status_code=400, detail="source and target are required")
    if source == target:
        return {"merged": 0, "message": "source and target are the same"}
    data = load_tags()
    merged_count = 0
    for path, entries in list(data.items()):
        names = [e["name"] for e in entries if e.get("name")]
        if source not in names:
            continue
        # Keep target's source if already present, else use source tag's source
        existing_target = next((e for e in entries if e.get("name") == target), None)
        source_entry = next((e for e in entries if e.get("name") == source), None)
        new_entries = [e for e in entries if e.get("name") != source]
        if not existing_target:
            new_entries.append({"name": target, "source": source_entry.get("source", SOURCE_MANUAL) if source_entry else SOURCE_MANUAL})
        data[path] = new_entries
        merged_count += 1
    save_tags(data)
    return {"merged": merged_count}


@router.delete("/globally")
async def delete_tag_globally(tag: str):
    """Remove this tag from every path. Paths with no tags left are removed from storage."""
    t = _normalize_tag(tag)
    if not t:
        raise HTTPException(status_code=400, detail="tag is required")
    data = load_tags()
    changed = 0
    for path, entries in list(data.items()):
        if not any(e.get("name") == t for e in entries):
            continue
        new_entries = [e for e in entries if e.get("name") != t]
        if not new_entries:
            del data[path]
        else:
            data[path] = new_entries
        changed += 1
    save_tags(data)
    return {"removed_from": changed}


@router.post("/bulk-add")
async def bulk_add_tag(request: BulkAddTagRequest):
    """Add a tag to multiple paths (merge with existing tags per path). New tag is manual."""
    tag = _normalize_tag(request.tag)
    if not tag:
        raise HTTPException(status_code=400, detail="tag is required")
    if not request.paths:
        raise HTTPException(status_code=400, detail="paths cannot be empty")
    data = load_tags()
    for p in request.paths:
        p = (p or "").strip()
        if not p:
            continue
        existing = data.get(p, [])
        names = tag_names(existing)
        if tag not in names:
            data[p] = existing + [{"name": tag, "source": SOURCE_MANUAL}]
    save_tags(data)
    return {"tag": tag, "paths_updated": len([p for p in request.paths if (p or "").strip()])}


@router.post("/suggest")
async def suggest_tags(path: str):
    """Suggest 3-5 tags from the embroidery design image (Ollama or OpenAI vision)."""
    if not path or not path.strip():
        raise HTTPException(status_code=400, detail="Path is required")
    if not _is_embroidery_file(path):
        raise HTTPException(
            status_code=400,
            detail="Path must be an embroidery file (e.g. .dst, .pes, .pec)",
        )
    from app.config import settings
    if not settings.ollama_base_url and not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="No vision provider configured. Set OLLAMA_BASE_URL or OPENAI_API_KEY.",
        )
    try:
        image_bytes = await _thumbnail_service.get_thumbnail(path, PREVIEW_SIZE)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get thumbnail: {e}")
    tags = await suggest_tags_from_image(image_bytes)
    if not tags:
        raise HTTPException(
            status_code=503,
            detail="Could not get suggestions from vision provider. Check Ollama/OpenAI is reachable.",
        )
    return {"path": path, "tags": tags}


@router.post("/run-auto-tag")
async def run_auto_tag(path: str = ""):
    """
    Run vision-based tagging on all untagged embroidery files under path (default: root).
    Only files that have no tags yet are processed.
    """
    from app.services.auto_tag_service import run_auto_tag_impl
    result = await run_auto_tag_impl(root_path=path)
    return result
