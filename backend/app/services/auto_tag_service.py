"""
Auto-tag embroidery files from vision: suggest_and_save_tags (single file),
run_auto_tag_impl (batch, only untagged). Used by run-auto-tag endpoint, nightly job, and upload.
"""
import logging
from pathlib import Path
from typing import List

from app.services.smb_service import SMBService
from app.services.file_service import FileService
from app.services.thumbnail_service import ThumbnailService, PREVIEW_SIZE
from app.services.vision_service import suggest_tags_from_image
from app.services.tag_storage import load_tags, save_tags, tag_names, SOURCE_AUTO

logger = logging.getLogger(__name__)

EMBROIDERY_EXTENSIONS = {
    ".dst", ".pes", ".pec", ".exp", ".vp3", ".jef", ".xxx", ".sew",
    ".dsz", ".tap", ".hus", ".pcs", ".ufo", ".emd", ".csd", ".10o",
}


def _is_embroidery_file(path: str) -> bool:
    return Path(path).suffix.lower() in EMBROIDERY_EXTENSIONS


def is_embroidery_file(path: str) -> bool:
    """Public check for embroidery file extension."""
    return _is_embroidery_file(path)


_smb = SMBService()
_thumbnail_service = ThumbnailService(_smb)
_file_service = FileService(_smb)


async def suggest_and_save_tags(path: str) -> List[str] | None:
    """
    Generate tags from the embroidery design image and save them (merge with existing).
    New suggested tags get source "auto"; existing tags keep their source.
    Returns list of tag names on success, None on failure.
    """
    if not _is_embroidery_file(path):
        return None
    try:
        image_bytes = await _thumbnail_service.get_thumbnail(path, PREVIEW_SIZE)
    except Exception as e:
        logger.warning("Auto-tag thumbnail failed for %s: %s", path, e)
        return None
    if len(image_bytes) < 100:
        logger.warning("Auto-tag skipped %s: thumbnail too small (placeholder?)", path)
        return None
    suggested = await suggest_tags_from_image(image_bytes)
    if not suggested:
        logger.info("Auto-tag no suggestions for %s (vision returned empty)", path)
        return None
    data = load_tags()
    existing = data.get(path, [])
    existing_names = {e["name"].lower(): e for e in existing}
    for name in suggested:
        name = (name or "").strip()
        if not name or name.lower() in existing_names:
            continue
        existing.append({"name": name, "source": SOURCE_AUTO})
        existing_names[name.lower()] = {"name": name, "source": SOURCE_AUTO}
    data[path] = existing
    save_tags(data)
    names = tag_names(existing)
    logger.info("Auto-tag saved %s -> %s", path, names)
    return names


def _list_embroidery_paths_under(root_path: str, max_items: int = 5000) -> List[str]:
    """List all embroidery file paths under root_path (recursive)."""
    root_path = (root_path or "").strip("/")
    items = _file_service._list_directory_recursive(root_path, max_items=max_items)
    return [
        item["path"]
        for item in items
        if not item.get("is_directory") and _is_embroidery_file(item.get("path", ""))
    ]


async def run_auto_tag_impl(root_path: str = "") -> dict:
    """
    Find untagged embroidery files under root_path, run vision and save tags.
    Returns {"processed": int, "skipped": int, "errors": list}.
    """
    all_paths = _list_embroidery_paths_under(root_path)
    data = load_tags()
    untagged = [p for p in all_paths if not tag_names(data.get(p, []))]
    skipped = len(all_paths) - len(untagged)
    processed = 0
    errors: List[str] = []
    for path in untagged:
        try:
            result = await suggest_and_save_tags(path)
            if result is not None:
                processed += 1
            else:
                errors.append(path)
        except Exception as e:
            logger.warning("Auto-tag failed for %s: %s", path, e)
            errors.append(f"{path}: {e}")
    return {"processed": processed, "skipped": skipped, "errors": errors}
