import os
import json
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter()

_app_data = os.environ.get("APP_DATA_DIR", "/app/data")
NOTES_FILE = os.environ.get("NOTES_FILE", os.path.join(_app_data, "notes.json"))


def load_notes() -> dict[str, str]:
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_notes(notes: dict[str, str]) -> None:
    os.makedirs(os.path.dirname(NOTES_FILE), exist_ok=True)
    with open(NOTES_FILE, "w") as f:
        json.dump(notes, f)


class NoteRequest(BaseModel):
    note: str = ""


class BatchNotesRequest(BaseModel):
    paths: List[str] = []


@router.get("")
async def get_note(path: str = ""):
    """Get note for a single path."""
    notes = load_notes()
    return {"path": path, "note": notes.get(path, "")}


@router.post("/batch")
async def get_notes_batch(request: BatchNotesRequest):
    """Get notes for multiple paths. Returns { notes: { path: string } }."""
    notes = load_notes()
    result = {p: notes.get(p, "") for p in request.paths}
    return {"notes": result}


@router.post("/{item_path:path}")
async def set_note_post(item_path: str, request: NoteRequest):
    """Set or update note for a path. Empty string clears."""
    notes = load_notes()
    note = (request.note or "").strip()
    if note:
        notes[item_path] = note
    elif item_path in notes:
        del notes[item_path]
    save_notes(notes)
    return {"path": item_path, "note": notes.get(item_path, "")}


@router.put("/{item_path:path}")
async def set_note_put(item_path: str, request: NoteRequest):
    """Set or update note for a path. Empty string clears."""
    return await set_note_post(item_path, request)


@router.delete("/{item_path:path}")
async def delete_note(item_path: str):
    """Remove note for a path."""
    notes = load_notes()
    if item_path in notes:
        del notes[item_path]
        save_notes(notes)
    return {"path": item_path, "note": ""}
