import asyncio
import base64
import logging
import re
from typing import List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def _trigger_ollama_pull() -> None:
    """Tell Ollama to pull the vision model. Runs in background; does not block."""
    url = (settings.ollama_base_url or "").rstrip("/")
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            await client.post(f"{url}/api/pull", json={"name": OLLAMA_VISION_MODEL})
        logger.info("Ollama pull %s completed", OLLAMA_VISION_MODEL)
    except Exception as e:
        logger.warning("Ollama pull %s failed: %s", OLLAMA_VISION_MODEL, e)

TAGS_PROMPT = """Describe this embroidery design in 3 to 5 short tags. Use single words or two words per tag, lowercase, comma-separated. Tags only, no explanation. Examples: flower, heart, logo, text, animal."""

OLLAMA_VISION_MODEL = "llava-phi3"
OPENAI_VISION_MODEL = "gpt-4o-mini"


def _parse_tags_response(text: str) -> List[str]:
    """Parse model output into a list of 3-5 cleaned tags."""
    if not text or not text.strip():
        return []
    # Split on comma, semicolon, newline; strip and lowercase; take alphanumeric + spaces, then collapse spaces
    parts = re.split(r"[,;\n]", text)
    tags = []
    for p in parts:
        t = re.sub(r"[^a-z0-9\s\-]", "", p.strip().lower()).strip()
        t = re.sub(r"\s+", " ", t)
        if t and t not in tags:
            tags.append(t)
    return tags[:5]


async def _suggest_via_ollama(image_bytes: bytes) -> List[str] | None:
    """Call Ollama chat API with image. Returns tag list or None on failure."""
    url = (settings.ollama_base_url or "").rstrip("/")
    if not url:
        return None
    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{url}/api/chat",
                json={
                    "model": OLLAMA_VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": TAGS_PROMPT,
                            "images": [b64],
                        }
                    ],
                    "stream": False,
                },
            )
            if r.status_code == 404 and "not found" in (r.text or "").lower():
                logger.info("Ollama model %s not found; triggering pull (try again in a few minutes)", OLLAMA_VISION_MODEL)
                asyncio.create_task(_trigger_ollama_pull())
                return None
            if r.status_code != 200:
                logger.warning(
                    "Ollama vision request failed: %s %s",
                    r.status_code,
                    (r.text or "")[:400],
                )
                return None
            data = r.json()
            err = data.get("error")
            if err:
                logger.warning("Ollama vision error in response: %s", err)
                return None
            message = data.get("message") or {}
            content = (message.get("content") or "").strip()
            out = _parse_tags_response(content)
            if not out:
                logger.debug("Ollama returned empty or unparseable content: %s", content[:200])
            return out
    except Exception as e:
        logger.warning("Ollama vision error: %s", e)
        return None


async def _suggest_via_openai(image_bytes: bytes) -> List[str] | None:
    """Call OpenAI vision API. Returns tag list or None on failure."""
    if not settings.openai_api_key:
        return None
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        response = await client.chat.completions.create(
            model=OPENAI_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": TAGS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=150,
        )
        text = (response.choices[0].message.content or "").strip()
        return _parse_tags_response(text)
    except Exception as e:
        logger.warning("OpenAI vision error: %s", e)
        return None


async def suggest_tags_from_image(image_bytes: bytes) -> List[str]:
    """
    Get 3-5 suggested tags from image bytes. Tries Ollama first if configured, then OpenAI.
    Returns empty list if no provider is available or both fail.
    """
    if settings.ollama_base_url:
        tags = await _suggest_via_ollama(image_bytes)
        if tags:
            return tags
    if settings.openai_api_key:
        tags = await _suggest_via_openai(image_bytes)
        if tags:
            return tags
    return []
