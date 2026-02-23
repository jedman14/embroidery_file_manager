from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.services.storage_factory import get_storage
from app.services.thumbnail_service import ThumbnailService, PREVIEW_SIZE

router = APIRouter()
thumbnail_service = ThumbnailService(get_storage())

@router.get("/preview/{full_path:path}")
async def get_preview(full_path: str):
    """Get or generate large preview for an embroidery file"""
    try:
        image_data = await thumbnail_service.get_thumbnail(full_path, PREVIEW_SIZE)
        return Response(
            content=image_data,
            media_type="image/png"
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{full_path:path}")
async def get_thumbnail(full_path: str):
    """Get or generate thumbnail for an embroidery file"""
    try:
        image_data = await thumbnail_service.get_thumbnail(full_path, (200, 200))
        return Response(
            content=image_data,
            media_type="image/png"
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
