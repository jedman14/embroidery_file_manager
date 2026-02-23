import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel

from app.services.smb_service import SMBService
from app.services.file_service import FileService
from app.services.auto_tag_service import suggest_and_save_tags, is_embroidery_file
from app.services.conversion_service import (
    convert_embroidery,
    is_readable_format,
    is_writable_format,
    READABLE_EXTENSIONS,
    WRITABLE_EXTENSIONS,
)

router = APIRouter()
smb_service = SMBService()
file_service = FileService(smb_service)


def _normalize_path(p: str) -> str:
    return "/".join(part for part in (p or "").strip().replace("\\", "/").strip("/").split("/") if part)

class FileItem(BaseModel):
    name: str
    path: str
    is_directory: bool
    size: int = 0
    modified: Optional[str] = None
    file_type: Optional[str] = None
    is_zip: bool = False

class MoveRequest(BaseModel):
    destination: str


class ConvertRequest(BaseModel):
    source_path: str
    target_format: str
    destination_path: Optional[str] = None


class PathsRequest(BaseModel):
    paths: List[str] = []

def _load_tags_for_search():
    """Return path -> list of tag names for file search (file_service expects string list)."""
    from app.services.tag_storage import load_tags, tag_names
    data = load_tags()
    return {path: tag_names(entries) for path, entries in data.items()}

@router.get("/search")
async def search_files(
    q: str = Query("", description="Search query"),
    root: str = Query("", description="Root path to search under"),
    semantic: bool = Query(False, description="Use fuzzy/semantic matching"),
    limit: int = Query(500, ge=1, le=2000),
):
    """Search all files and folders. When semantic=True, matches typos and related terms."""
    try:
        path_tags = _load_tags_for_search()
        result = await file_service.search_all(
            q=q, root=root, semantic=semantic, path_tags=path_tags, limit=limit
        )
        return result
    except Exception as e:
        return {"path": root, "items": [], "total": 0, "error": str(e)}

@router.get("/convert/formats")
async def get_convert_formats():
    """Return readable and writable embroidery extensions for the converter."""
    return {"readable": READABLE_EXTENSIONS, "writable": WRITABLE_EXTENSIONS}


@router.post("/convert")
async def convert_embroidery_file(request: ConvertRequest):
    """Convert an embroidery file to another format. Never overwrites the source."""
    src = _normalize_path(request.source_path)
    tgt_fmt = (request.target_format or "").strip().lower()
    if not tgt_fmt.startswith("."):
        tgt_fmt = "." + tgt_fmt

    if not is_writable_format(tgt_fmt):
        raise HTTPException(status_code=400, detail=f"Unsupported target format: {request.target_format}")

    if not smb_service.file_exists(src):
        raise HTTPException(status_code=404, detail="File not found")

    ext = Path(src).suffix.lower()
    if not is_readable_format(ext):
        raise HTTPException(status_code=400, detail=f"Unsupported source format: {ext}")

    try:
        source_bytes = smb_service.get_file(src)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot read file: {e}")

    try:
        converted = convert_embroidery(source_bytes, ext, tgt_fmt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if request.destination_path is not None:
        dest = _normalize_path(request.destination_path)
        if dest == src:
            raise HTTPException(status_code=400, detail="Destination cannot be the same as source (original file is never overwritten)")
        try:
            await file_service.upload_file(dest, converted)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {"path": dest, "size": len(converted)}

    # Stream response for download
    base = Path(src).stem
    filename = f"{base}{tgt_fmt}"
    return StreamingResponse(
        BytesIO(converted),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("")
async def list_files(path: str = ""):
    """List contents of a directory"""
    try:
        items = await file_service.list_directory(path)
        return {"path": path, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/info")
async def get_files_info(request: PathsRequest):
    """Get file metadata for a list of paths (for thumbnail grid, etc.)."""
    try:
        items = await file_service.get_files_info(request.paths or [])
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{full_path:path}/download")
async def download_file(full_path: str):
    """Download a file as streaming response"""
    try:
        return await file_service.stream_file(full_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{full_path:path}/contents")
async def get_zip_contents(full_path: str):
    """List contents of a zip file without extracting"""
    try:
        result = await file_service.get_zip_contents(full_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{full_path:path}/extract")
async def extract_zip(full_path: str, destination: str = ""):
    """Extract a zip file"""
    try:
        result = await file_service.extract_zip(full_path, destination)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{full_path:path}/move")
async def move_file(full_path: str, request: MoveRequest):
    """Move a file to a new location"""
    try:
        result = await file_service.move_file(full_path, request.destination)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{full_path:path}")
async def get_file(full_path: str):
    """Download a file or get file details"""
    try:
        return await file_service.get_file_info(full_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def upload_file(path: str, file: UploadFile = File(...)):
    """Upload a file. path = destination directory; file.filename = name."""
    try:
        content = await file.read()
        full_path = f"{path}/{file.filename}" if path else file.filename
        result = await file_service.upload_file(full_path, content)
        if is_embroidery_file(full_path):
            asyncio.create_task(suggest_and_save_tags(full_path))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/folder")
async def create_folder(path: str):
    """Create a new folder"""
    try:
        result = await file_service.create_folder(path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{full_path:path}")
async def rename_file(full_path: str, new_name: str):
    """Rename a file"""
    try:
        result = await file_service.rename_file(full_path, new_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("")
async def delete_files(request: Request):
    """Delete a file or multiple files"""
    try:
        body = await request.json()
        items = body.get('items', [])
        if items:
            result = await file_service.delete_files(items)
        else:
            result = {"success": False, "deleted": [], "error": "No items provided"}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{full_path:path}")
async def delete_file(full_path: str):
    """Delete a single file"""
    try:
        result = await file_service.delete_file(full_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
