"""Build storage backend from config (SMB only, local only, or both via router)."""
from app.config import settings
from app.services.smb_service import SMBService
from app.services.local_storage_service import LocalStorageService
from app.services.storage_router import StorageRouter

_smb: SMBService | None = None
_storage = None


def get_smb_service() -> SMBService:
    """Return shared SMB service (for health check when SMB in use)."""
    global _smb
    if _smb is None:
        _smb = SMBService()
    return _smb


def get_storage():
    """
    Return the active storage backend: StorageRouter (when both),
    LocalStorageService (when local only), or SMBService (when smb only).
    """
    global _storage
    if _storage is not None:
        return _storage
    src = (settings.file_source or "smb").strip().lower()
    smb = get_smb_service()
    if src == "both":
        local = LocalStorageService()
        _storage = StorageRouter(smb, local)
    elif src == "local":
        _storage = LocalStorageService()
    else:
        _storage = smb
    return _storage
