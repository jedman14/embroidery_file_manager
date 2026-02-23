import os
import re
import unicodedata
import zipfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from rapidfuzz import fuzz
from app.services.smb_service import SMBService

EMBROIDERY_EXTENSIONS = {
    '.dst': 'Tajima',
    '.pes': 'Brother',
    '.pec': 'Brother',
    '.exp': 'Melco',
    '.vp3': 'Viking',
    '.vip': 'Viking',
    '.jef': 'Janome',
    '.xxx': 'Wilcom',
    '.hus': 'Husqvarna',
    '.ufo': 'UFO',
    '.emd': 'Elna',
    '.csd': 'Singer',
    '.10o': 'Pfaff',
    '.ofm': 'Brother',
    '.pcs': 'Pfaff',
    '.vpk': 'Pfaff'
}

class FileService:
    def __init__(self, smb_service: SMBService):
        self.smb = smb_service
    
    def get_file_type(self, filename: str) -> str:
        """Detect embroidery file type from extension"""
        ext = Path(filename).suffix.lower()
        return EMBROIDERY_EXTENSIONS.get(ext, 'Unknown')
    
    def is_zip_file(self, filename: str) -> bool:
        """Check if file is a zip archive"""
        return filename.lower().endswith('.zip')
    
    async def list_directory(self, path: str) -> List[dict]:
        """List directory contents with file type detection"""
        items = self.smb.list_directory(path)
        
        for item in items:
            item['file_type'] = self.get_file_type(item['name'])
            item['is_zip'] = self.is_zip_file(item['name'])
        
        return sorted(items, key=lambda x: (not x['is_directory'], x['name'].lower()))

    def _list_directory_recursive(self, path: str, max_items: int = 6000) -> List[dict]:
        """List all items under path using level-order BFS so every folder is represented before any subtree is exhausted."""
        root = (path or "").strip('/')
        items = []
        try:
            from collections import deque
            queue = deque([root] if root else [""])
            while queue and len(items) < max_items:
                dir_path = queue.popleft()
                for item in self.smb.list_directory(dir_path):
                    if item['name'] in ('.', '..'):
                        continue
                    item['file_type'] = self.get_file_type(item['name'])
                    item['is_zip'] = self.is_zip_file(item['name'])
                    items.append(item)
                    if len(items) >= max_items:
                        return items[:max_items]
                    if item.get('is_directory'):
                        queue.append(item['path'])
        except Exception:
            pass
        return items

    def _normalize(self, s: str) -> str:
        """Normalize for search: strip, lowercase, Unicode NFC."""
        if not s:
            return ""
        return unicodedata.normalize("NFC", (s or "").strip().lower())

    def _normalize_path_key(self, p: str) -> str:
        """Normalize path for consistent tag lookup: single forward slashes, strip."""
        if not p:
            return ""
        s = (p or "").strip().replace("\\", "/")
        return "/".join(part for part in s.split("/") if part)

    def _search_terms(self, q: str) -> list:
        """Normalize query into list of search terms."""
        s = self._normalize(q)
        if not s:
            return []
        return [t for t in re.split(r"\s+", s) if len(t) >= 1]

    def _score_term_in_text(self, term: str, text: str, fuzzy: bool) -> tuple[float, bool]:
        """
        Score how well a single term matches text. Returns (score, is_solid).
        is_solid = True means exact or substring match (not fuzzy-only).
        """
        if not term or not text:
            return 0.0, False
        # Exact equality (e.g. "abc" vs "abc")
        if term == text:
            return 200.0, True
        if term in text:
            if re.search(r"(^|[^\w])" + re.escape(term) + r"([^\w]|$)", text):
                return 120.0, True
            return 60.0, True
        if fuzzy:
            r = fuzz.partial_ratio(term, text)
            return ((r / 100.0) * 25.0 if r >= 70 else 0.0, False)
        return 0.0, False

    def _score_item(
        self,
        item: dict,
        terms: list,
        path_tags: dict,
        semantic: bool,
        tag_to_paths: Optional[dict] = None,
    ) -> float:
        """Return a relevance score for the item. 0 = no match.
        path_tags should be keyed by normalized path. tag_to_paths maps normalized tag -> set of normalized paths.
        """
        raw_name = (item.get("name") or "").strip() or os.path.basename((item.get("path") or ""))
        name = self._normalize(raw_name)
        path_lower = self._normalize(item.get("path") or "")
        path_norm = self._normalize_path_key(item.get("path") or "")
        raw_tags = path_tags.get(path_norm) or path_tags.get(item.get("path", ""), [])
        tags_list = raw_tags if isinstance(raw_tags, list) else []
        tags_str = " ".join(self._normalize(str(t)) for t in tags_list)
        tags_each = [self._normalize(str(t)) for t in tags_list]

        total = 0.0
        any_solid = False
        all_matched = True
        for term in terms:
            name_score, name_solid = self._score_term_in_text(term, name, semantic)
            path_score, path_solid = self._score_term_in_text(term, path_lower, semantic)
            path_score *= 0.8
            tag_score = 0.0
            tag_solid = False
            for t in tags_each:
                if term == t:
                    tag_score = max(tag_score, 200.0)
                    tag_solid = True
                elif term in t:
                    tag_score = max(tag_score, 70.0)
                    tag_solid = True
            if semantic and tag_score == 0 and tags_str:
                r = fuzz.partial_ratio(term, tags_str)
                if r >= 70:
                    tag_score = (r / 100.0) * 25.0
            best = max(name_score, path_score, tag_score)
            if best <= 0:
                all_matched = False
            if name_solid or path_solid or tag_solid:
                any_solid = True
            total += best
        if not all_matched and len(terms) > 1:
            return 0.0
        # When fuzzy is on, require at least one solid match to cut noise
        if semantic and len(terms) >= 1 and not any_solid and total > 0:
            return 0.0
        full_q = " ".join(terms)
        if full_q in name:
            total += 80.0
        if full_q in path_lower:
            total += 40.0
        # Strong boost: query is exactly a tag and this item has that tag (reliable tag search)
        if tag_to_paths and len(terms) == 1 and path_norm in tag_to_paths.get(terms[0], set()):
            total += 400.0
        return total

    async def search_all(
        self,
        q: str,
        root: str = "",
        semantic: bool = False,
        path_tags: Optional[dict] = None,
        limit: int = 500,
    ) -> dict:
        """
        Search files and folders by name, path, and tags.
        Returns results sorted by relevance score. Empty query returns no results.
        semantic=True enables fuzzy matching (typos, partial words).
        """
        path_tags = path_tags or {}
        try:
            all_items = self._list_directory_recursive(root or "", max_items=6000)
        except Exception:
            return {"path": root, "items": [], "total": 0}

        terms = self._search_terms(q)
        if not terms:
            return {"path": root, "items": [], "total": 0}

        # Normalize path keys so tag lookup matches regardless of slash/encoding
        path_tags_norm = {}
        for k, v in path_tags.items():
            if isinstance(v, list):
                path_tags_norm[self._normalize_path_key(k)] = v
        path_tags_norm.update(path_tags)

        # Reverse index: tag (normalized) -> set of normalized paths (for "search by tag")
        tag_to_paths = {}
        for path, tag_list in path_tags.items():
            if not isinstance(tag_list, list):
                continue
            pnorm = self._normalize_path_key(path)
            for t in tag_list:
                tnorm = self._normalize(str(t))
                if tnorm:
                    tag_to_paths.setdefault(tnorm, set()).add(pnorm)

        min_score = 30.0
        scored: list = []
        for item in all_items:
            score = self._score_item(item, terms, path_tags_norm, semantic, tag_to_paths)
            if score >= min_score:
                scored.append((score, item))

        scored.sort(key=lambda x: (-x[0], (x[1].get("path") or "")))
        items = [item for _, item in scored[:limit]]
        return {"path": root, "items": items, "total": len(items)}
    
    async def get_file_info(self, path: str) -> dict:
        """Get detailed file information"""
        if not self.smb.file_exists(path):
            raise FileNotFoundError(f"File not found: {path}")
        
        items = self.smb.list_directory(os.path.dirname(path))
        filename = os.path.basename(path)
        
        for item in items:
            if item['name'] == filename:
                item['file_type'] = self.get_file_type(filename)
                item['is_zip'] = self.is_zip_file(filename)
                return item
        
        return {
            "name": filename,
            "path": path,
            "file_type": self.get_file_type(filename),
            "is_zip": self.is_zip_file(filename)
        }

    async def get_files_info(self, paths: List[str]) -> List[dict]:
        """Get file metadata for multiple paths. Groups by parent dir to minimize list_directory calls."""
        if not paths:
            return []
        # Normalize and dedupe paths
        want = {}
        for p in paths:
            p = (p or "").strip()
            if p:
                want[p] = True
        paths = list(want.keys())
        by_parent = {}
        for p in paths:
            parent = os.path.dirname(p)
            by_parent.setdefault(parent, []).append(p)
        result = []
        for parent, child_paths in by_parent.items():
            items = self.smb.list_directory(parent)
            for item in items:
                if item.get("path") in child_paths:
                    item["file_type"] = self.get_file_type(item["name"])
                    item["is_zip"] = self.is_zip_file(item["name"])
                    result.append(item)
        # Preserve requested order; include any path we didn't find with minimal info
        path_to_item = {r["path"]: r for r in result}
        ordered = []
        for p in paths:
            if p in path_to_item:
                ordered.append(path_to_item[p])
            else:
                ordered.append({
                    "name": os.path.basename(p),
                    "path": p,
                    "is_directory": False,
                    "size": 0,
                    "modified": None,
                    "file_type": self.get_file_type(os.path.basename(p)),
                    "is_zip": self.is_zip_file(os.path.basename(p)),
                })
        return ordered
    
    async def stream_file(self, path: str):
        """Stream file content for download"""
        data = self.smb.get_file(path)
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            BytesIO(data),
            media_type='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename="{os.path.basename(path)}"'}
        )
    
    async def upload_file(self, path: str, data: bytes) -> dict:
        """Upload a file to SMB share"""
        filename = os.path.basename(path)
        dir_path = os.path.dirname(path)
        
        if dir_path and not self.smb.file_exists(dir_path):
            self.smb.create_directory_recursive(dir_path)
        
        self.smb.put_file(path, data)
        
        return {
            "success": True,
            "name": filename,
            "path": path,
            "size": len(data)
        }
    
    async def rename_file(self, path: str, new_name: str) -> dict:
        """Rename a file"""
        dir_path = os.path.dirname(path)
        new_path = os.path.join(dir_path, new_name).replace('\\', '/')
        
        self.smb.rename(path, new_path)
        
        return {
            "success": True,
            "old_path": path,
            "new_path": new_path
        }
    
    async def create_folder(self, path: str) -> dict:
        """Create a new folder"""
        self.smb.create_directory(path)
        return {
            "success": True,
            "path": path,
            "name": os.path.basename(path)
        }
    
    async def delete_file(self, path: str) -> dict:
        """Delete a single file or folder"""
        try:
            if self.smb.is_directory(path):
                self.smb.delete_directory_recursive(path)
            else:
                self.smb.delete_file(path)
            return {"success": True, "deleted": [path]}
        except Exception as e:
            return {"success": False, "deleted": [], "error": str(e)}
    
    async def delete_files(self, paths: List[str]) -> dict:
        """Delete multiple files and folders"""
        deleted = []
        errors = []
        for path in paths:
            try:
                if self.smb.is_directory(path):
                    self.smb.delete_directory_recursive(path)
                else:
                    self.smb.delete_file(path)
                deleted.append(path)
            except Exception as e:
                errors.append(f"{path}: {str(e)}")
        
        return {"success": len(errors) == 0, "deleted": deleted, "errors": errors}
    
    async def move_file(self, source: str, destination: str) -> dict:
        """Move a file to a new location"""
        filename = os.path.basename(source)
        
        if not destination.endswith(filename):
            destination = os.path.join(destination, filename).replace('\\', '/')
        
        self.smb.move(source, destination)
        
        return {
            "success": True,
            "source": source,
            "destination": destination
        }
    
    async def extract_zip(self, zip_path: str, destination: str = "") -> dict:
        """Extract a zip file"""
        zip_data = self.smb.get_file(zip_path)
        
        if not destination:
            destination = zip_path.rsplit('.', 1)[0]
        
        destination = destination.strip('/')
        self.smb.create_directory_recursive(destination)
        
        extracted = []
        created_dirs = set()
        
        with zipfile.ZipFile(BytesIO(zip_data)) as zf:
            for member in zf.namelist():
                if member.endswith('/'):
                    continue
                
                member_path = f"{destination}/{member}".replace('\\', '/')
                parent_dir = os.path.dirname(member_path)
                if parent_dir and parent_dir not in created_dirs:
                    self.smb.create_directory_recursive(parent_dir)
                    created_dirs.add(parent_dir)
                
                data = zf.read(member)
                self.smb.put_file(member_path, data)
                extracted.append(member_path)
        
        return {
            "success": True,
            "extracted": extracted,
            "destination": destination
        }
    
    async def get_zip_contents(self, zip_path: str) -> dict:
        """List contents of a zip file without extracting"""
        zip_data = self.smb.get_file(zip_path)
        
        contents = []
        
        with zipfile.ZipFile(BytesIO(zip_data)) as zf:
            for member in zf.namelist():
                if member.endswith('/'):
                    continue
                
                info = zf.getinfo(member)
                contents.append({
                    "name": member,
                    "path": f"{zip_path}/{member}",
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "is_directory": member.endswith('/'),
                    "file_type": self.get_file_type(member),
                    "is_zip": member.lower().endswith('.zip')
                })
        
        return {
            "path": zip_path,
            "items": sorted(contents, key=lambda x: (not x['is_directory'], x['name'].lower())),
            "total": len(contents)
        }
