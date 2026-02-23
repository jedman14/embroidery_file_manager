"""Routes file operations to SMB and/or local backend under /files (smb -> /files/smb, local -> /files/local)."""
from typing import List, Tuple, Any, Optional

from app.config import settings
from app.services.smb_service import SMBService
from app.services.local_storage_service import LocalStorageService


def _norm(p: str) -> str:
    return (p or "").strip().replace("\\", "/").strip("/")


class StorageRouter:
    """
    Presents a single root /files. When file_source is "both", list("") returns
    smb and local as folders; paths are prefixed smb/ or local/. When single
    source, no prefix.
    """

    PREFIX_SMB = "smb"
    PREFIX_LOCAL = "local"

    def __init__(
        self,
        smb_service: SMBService,
        local_service: Optional[LocalStorageService] = None,
    ):
        self._smb = smb_service
        self._local = local_service
        self._both = (settings.file_source or "").lower() == "both" and self._local is not None

    def _route(self, path: str) -> Tuple[Optional[str], Any, str]:
        """
        Return (prefix, backend, relative_path). prefix is None when single source.
        """
        p = _norm(path)
        if self._both:
            if p == "" or p == self.PREFIX_SMB:
                return self.PREFIX_SMB, self._smb, ""
            if p == self.PREFIX_LOCAL:
                return self.PREFIX_LOCAL, self._local, ""
            if p.startswith(self.PREFIX_SMB + "/"):
                return self.PREFIX_SMB, self._smb, p[len(self.PREFIX_SMB) + 1 :]
            if p.startswith(self.PREFIX_LOCAL + "/"):
                return self.PREFIX_LOCAL, self._local, p[len(self.PREFIX_LOCAL) + 1 :]
            # Path doesn't start with smb/ or local/ - treat as SMB for backward compat in edge case
            return self.PREFIX_SMB, self._smb, p
        if (settings.file_source or "").lower() == "local" and self._local is not None:
            return None, self._local, p
        return None, self._smb, p

    def _with_prefix(self, prefix: Optional[str], path: str) -> str:
        if not prefix or not path:
            return path or prefix or ""
        return f"{prefix}/{path}" if path else prefix

    def list_directory(self, path: str) -> List[dict]:
        p = _norm(path)
        if self._both and p == "":
            return [
                {"name": "smb", "path": self.PREFIX_SMB, "is_directory": True, "size": 0, "modified": None},
                {"name": "local", "path": self.PREFIX_LOCAL, "is_directory": True, "size": 0, "modified": None},
            ]
        prefix, backend, rel = self._route(path)
        items = backend.list_directory(rel)
        if prefix:
            for item in items:
                item["path"] = self._with_prefix(prefix, item["path"])
        return items

    def get_file(self, path: str) -> bytes:
        _, backend, rel = self._route(path)
        return backend.get_file(rel)

    def put_file(self, path: str, data: bytes) -> bool:
        _, backend, rel = self._route(path)
        return backend.put_file(rel, data)

    def delete_file(self, path: str) -> bool:
        _, backend, rel = self._route(path)
        return backend.delete_file(rel)

    def delete_directory(self, path: str) -> bool:
        _, backend, rel = self._route(path)
        return backend.delete_directory(rel)

    def delete_directory_recursive(self, path: str) -> bool:
        _, backend, rel = self._route(path)
        return backend.delete_directory_recursive(rel)

    def _copy_recursive(self, backend_from: Any, backend_to: Any, rel_from: str, rel_to: str) -> None:
        if backend_from.is_directory(rel_from):
            backend_to.create_directory_recursive(rel_to)
            for item in backend_from.list_directory(rel_from):
                sub_from = f"{rel_from}/{item['name']}".strip("/") if rel_from else item["name"]
                sub_to = f"{rel_to}/{item['name']}".strip("/") if rel_to else item["name"]
                self._copy_recursive(backend_from, backend_to, sub_from, sub_to)
        else:
            data = backend_from.get_file(rel_from)
            backend_to.put_file(rel_to, data)

    def rename(self, old_path: str, new_path: str) -> bool:
        op, obackend, orel = self._route(old_path)
        np, nbackend, nrel = self._route(new_path)
        if obackend is nbackend:
            return obackend.rename(orel, nrel)
        # Cross-backend: copy then delete
        if obackend.is_directory(orel):
            self._copy_recursive(obackend, nbackend, orel, nrel)
            obackend.delete_directory_recursive(orel)
        else:
            data = obackend.get_file(orel)
            parent = nrel.rsplit("/", 1)[0] if "/" in nrel else ""
            if parent:
                nbackend.create_directory_recursive(parent)
            nbackend.put_file(nrel, data)
            obackend.delete_file(orel)
        return True

    def move(self, source_path: str, dest_path: str) -> bool:
        return self.rename(source_path, dest_path)

    def create_directory(self, path: str) -> bool:
        _, backend, rel = self._route(path)
        return backend.create_directory(rel)

    def create_directory_recursive(self, path: str) -> bool:
        _, backend, rel = self._route(path)
        return backend.create_directory_recursive(rel)

    def file_exists(self, path: str) -> bool:
        _, backend, rel = self._route(path)
        return backend.file_exists(rel)

    def is_directory(self, path: str) -> bool:
        _, backend, rel = self._route(path)
        return backend.is_directory(rel)

    def get_file_size(self, path: str) -> int:
        _, backend, rel = self._route(path)
        return backend.get_file_size(rel)
