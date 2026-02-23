"""Local filesystem storage backend. All paths are relative to a configurable root."""
import os
from pathlib import Path
from typing import List
from datetime import datetime

from app.config import settings


def _norm(p: str) -> str:
    return (p or "").strip().replace("\\", "/").strip("/")


class LocalStorageService:
    """Storage backend that reads/writes under a single root directory."""

    def __init__(self, root: str | None = None):
        self._root = Path((root or settings.local_mount_path or "").rstrip("/")).resolve()

    def _resolve(self, path: str) -> Path:
        """Resolve path under root; raise if it escapes root."""
        rel = _norm(path)
        if not rel:
            return self._root
        full = (self._root / rel).resolve()
        try:
            full.relative_to(self._root)
        except ValueError:
            raise PermissionError(f"Path escapes root: {path}")
        return full

    def list_directory(self, path: str) -> List[dict]:
        """List contents of a directory."""
        base = self._resolve(path)
        if not base.is_dir():
            raise NotADirectoryError(str(base))
        items = []
        for entry in sorted(base.iterdir(), key=lambda e: (e.is_file(), e.name.lower())):
            name = entry.name
            rel = base / name
            try:
                item_path = rel.relative_to(self._root)
            except ValueError:
                continue
            item_path_str = str(item_path).replace("\\", "/")
            try:
                stat = entry.stat()
                mtime = stat.st_mtime
                modified = datetime.fromtimestamp(mtime).isoformat() if mtime else None
                size = stat.st_size if entry.is_file() else 0
            except OSError:
                modified = None
                size = 0
            items.append({
                "name": name,
                "path": item_path_str,
                "is_directory": entry.is_dir(),
                "size": size,
                "modified": modified,
            })
        return items

    def get_file(self, path: str) -> bytes:
        """Read file content."""
        full = self._resolve(path)
        if full.is_dir():
            raise IsADirectoryError(str(full))
        return full.read_bytes()

    def put_file(self, path: str, data: bytes) -> bool:
        """Write file."""
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return True

    def delete_file(self, path: str) -> bool:
        """Delete file."""
        full = self._resolve(path)
        if full.is_dir():
            return False
        full.unlink()
        return True

    def delete_directory(self, path: str) -> bool:
        """Delete empty directory."""
        full = self._resolve(path)
        if not full.is_dir():
            return False
        full.rmdir()
        return True

    def delete_directory_recursive(self, path: str) -> bool:
        """Delete directory and all contents."""
        full = self._resolve(path)
        if not full.is_dir():
            return False
        import shutil
        shutil.rmtree(full)
        return True

    def rename(self, old_path: str, new_path: str) -> bool:
        """Rename or move a file or directory."""
        src = self._resolve(old_path)
        dest = self._resolve(new_path)
        src.rename(dest)
        return True

    def move(self, source_path: str, dest_path: str) -> bool:
        """Move a file or directory."""
        return self.rename(source_path, dest_path)

    def create_directory(self, path: str) -> bool:
        """Create directory."""
        full = self._resolve(path)
        full.mkdir(parents=False, exist_ok=True)
        return True

    def create_directory_recursive(self, path: str) -> bool:
        """Create directory and all parent directories."""
        full = self._resolve(path)
        full.mkdir(parents=True, exist_ok=True)
        return True

    def file_exists(self, path: str) -> bool:
        """Check if path exists (file or directory)."""
        full = self._resolve(path)
        return full.exists()

    def is_directory(self, path: str) -> bool:
        """Check if path is a directory."""
        full = self._resolve(path)
        if not full.exists():
            return False
        return full.is_dir()

    def get_file_size(self, path: str) -> int:
        """Get file size in bytes."""
        full = self._resolve(path)
        if full.is_dir():
            return 0
        return full.stat().st_size
