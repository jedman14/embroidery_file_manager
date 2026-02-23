"""
Re-key tags, notes, and folder logos when a file or directory is moved/renamed
so metadata stays associated with the file.
"""


def _norm_path(p: str) -> str:
    return (p or "").strip().replace("\\", "/").strip("/")


def _keys_to_migrate(data: dict, old_path: str, new_path: str) -> list[tuple[str, str]]:
    """Return list of (old_key, new_key) for exact match and all keys under old_path."""
    old_norm = _norm_path(old_path)
    new_norm = _norm_path(new_path)
    if not old_norm:
        return []
    out = []
    for key in list(data.keys()):
        k_norm = _norm_path(key)
        if k_norm == old_norm:
            out.append((key, new_norm))
        elif k_norm.startswith(old_norm + "/"):
            suffix = k_norm[len(old_norm) + 1 :]
            out.append((key, f"{new_norm}/{suffix}" if new_norm else suffix))
    return out


def migrate_metadata(old_path: str, new_path: str) -> None:
    """
    Re-key tags, notes, and folder logos from old_path to new_path.
    Handles exact key and directory moves (all keys under old_path).
    """
    old_norm = _norm_path(old_path)
    new_norm = _norm_path(new_path)
    if not old_norm or old_norm == new_norm:
        return

    # Tags
    from app.services.tag_storage import load_tags, save_tags
    tags_data = load_tags()
    for old_k, new_k in _keys_to_migrate(tags_data, old_path, new_path):
        tags_data[new_k] = tags_data.pop(old_k, [])
    save_tags(tags_data)

    # Notes
    from app.api.notes import load_notes, save_notes
    notes_data = load_notes()
    for old_k, new_k in _keys_to_migrate(notes_data, old_path, new_path):
        notes_data[new_k] = notes_data.pop(old_k, "")
    save_notes(notes_data)

    # Folder logos (path -> logo_url; only path key changes)
    from app.api.logos import load_logos, save_logos
    logos_data = load_logos()
    for old_k, new_k in _keys_to_migrate(logos_data, old_path, new_path):
        logos_data[new_k] = logos_data.pop(old_k, "")
    save_logos(logos_data)
