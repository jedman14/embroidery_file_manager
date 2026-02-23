import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import files, thumbnails, tags, logos
from app.config import settings
from app.services.auto_tag_service import run_auto_tag_impl
from app.services.vision_service import OLLAMA_VISION_MODEL

logger = logging.getLogger(__name__)


async def _ensure_ollama_model():
    """Tell Ollama to pull the vision model if needed (fire-and-forget, does not block)."""
    url = (settings.ollama_base_url or "").rstrip("/")
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{url}/api/pull", json={"name": OLLAMA_VISION_MODEL})
            if r.status_code == 200:
                logger.info("Ollama model %s pull triggered or already present", OLLAMA_VISION_MODEL)
            else:
                logger.warning("Ollama pull %s: %s %s", OLLAMA_VISION_MODEL, r.status_code, r.text[:200])
    except Exception as e:
        logger.debug("Ollama pull check skipped: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ollama_base_url:
        asyncio.create_task(_ensure_ollama_model())
    scheduler = AsyncIOScheduler()
    async def nightly_auto_tag():
        try:
            await run_auto_tag_impl("")
        except Exception:
            pass
    scheduler.add_job(
        nightly_auto_tag,
        "cron",
        hour=settings.tag_cron_hour,
        minute=settings.tag_cron_minute,
        id="nightly_auto_tag",
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Embroidery File Manager API",
    description="API for managing embroidery files via Samba share",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(thumbnails.router, prefix="/api/thumbnails", tags=["thumbnails"])
app.include_router(tags.router, prefix="/api/tags", tags=["tags"])
app.include_router(logos.router, prefix="/api/logos", tags=["logos"])

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "smb_connected": True}
