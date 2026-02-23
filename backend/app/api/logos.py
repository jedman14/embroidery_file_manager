import os
import json
from io import BytesIO
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image

router = APIRouter()

_app_data = os.environ.get('APP_DATA_DIR', '/app/data')
LOGOS_FILE = os.environ.get('LOGOS_FILE', os.path.join(_app_data, 'folder_logos.json'))
LOGOS_DIR = os.environ.get('LOGOS_DIR', os.path.join(_app_data, 'logos'))
LOGO_SIZE = (128, 128)

def load_logos():
    if os.path.exists(LOGOS_FILE):
        try:
            with open(LOGOS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_logos(logos):
    os.makedirs(os.path.dirname(LOGOS_FILE), exist_ok=True)
    with open(LOGOS_FILE, 'w') as f:
        json.dump(logos, f)

def resize_logo(content: bytes) -> bytes:
    """Resize and pad image to a consistent square logo."""
    try:
        img = Image.open(BytesIO(content))
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
            background = Image.new('RGBA', LOGO_SIZE, (255, 255, 255, 0))
        else:
            img = img.convert('RGB')
            background = Image.new('RGB', LOGO_SIZE, (255, 255, 255))

        img.thumbnail(LOGO_SIZE, Image.Resampling.LANCZOS)

        offset = ((LOGO_SIZE[0] - img.width) // 2, (LOGO_SIZE[1] - img.height) // 2)
        background.paste(img, offset)

        output = BytesIO()
        background.save(output, format='PNG')
        return output.getvalue()
    except Exception:
        return content

class LogoRequest(BaseModel):
    logo_url: str

@router.get("")
async def get_logos():
    """Get all folder logos"""
    return load_logos()

# IMPORTANT: /files/{filename} must be defined BEFORE /{folder_path:path}
# so that the path converter doesn't swallow it.
@router.get("/files/{filename}")
async def get_logo_file(filename: str):
    """Serve logo files"""
    filepath = os.path.join(LOGOS_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="image/png")
    raise HTTPException(status_code=404, detail="Logo not found")

@router.get("/{folder_path:path}")
async def get_folder_logo(folder_path: str):
    """Get logo for a specific folder"""
    logos = load_logos()
    return {"path": folder_path, "logo_url": logos.get(folder_path, "")}

@router.post("/{folder_path:path}/upload")
async def upload_folder_logo(folder_path: str, file: UploadFile = File(...)):
    """Upload a logo image for a folder"""
    os.makedirs(LOGOS_DIR, exist_ok=True)

    content = await file.read()
    content = resize_logo(content)

    safe_name = folder_path.replace('/', '_').replace(' ', '_')
    filename = f"{safe_name}_{os.urandom(8).hex()}.png"
    filepath = os.path.join(LOGOS_DIR, filename)

    with open(filepath, 'wb') as f:
        f.write(content)

    logo_url = f"/api/logos/files/{filename}"

    logos = load_logos()
    old_url = logos.get(folder_path, "")
    if old_url.startswith('/api/logos/files/'):
        old_file = os.path.join(LOGOS_DIR, old_url.split('/')[-1])
        if os.path.exists(old_file):
            os.remove(old_file)

    logos[folder_path] = logo_url
    save_logos(logos)

    return {"path": folder_path, "logo_url": logo_url}

@router.post("/{folder_path:path}")
async def set_folder_logo_url(folder_path: str, request: LogoRequest):
    """Set logo URL for a folder"""
    logos = load_logos()
    logos[folder_path] = request.logo_url
    save_logos(logos)
    return {"path": folder_path, "logo_url": request.logo_url}

@router.delete("/{folder_path:path}")
async def delete_folder_logo(folder_path: str):
    """Remove logo for a folder"""
    logos = load_logos()
    if folder_path in logos:
        logo_url = logos[folder_path]
        if logo_url.startswith('/api/logos/files/'):
            filename = logo_url.split('/')[-1]
            filepath = os.path.join(LOGOS_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        del logos[folder_path]
        save_logos(logos)
    return {"path": folder_path, "logo_url": ""}
