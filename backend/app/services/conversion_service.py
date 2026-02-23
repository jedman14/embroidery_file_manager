"""
Convert embroidery files between formats using pyembroidery.
Never overwrites the source; destination is validated by the API layer.
"""
import logging
import os
import tempfile
from pathlib import Path

import pyembroidery

logger = logging.getLogger(__name__)

# Pyembroidery write-capable formats (valid conversion targets)
WRITABLE_EXTENSIONS = [
    ".pes", ".dst", ".exp", ".jef", ".vp3", ".pec", ".xxx",
    ".u01", ".tbf", ".gcode",
]

# Extensions pyembroidery can read (union of writable + read-only in library)
# .emb = Embroidery by TM (try read; may not be supported by pyembroidery)
READABLE_EXTENSIONS = [
    ".pes", ".dst", ".exp", ".jef", ".vp3", ".pec", ".xxx",
    ".u01", ".tbf", ".gcode",
    ".10o", ".100", ".bro", ".dat", ".dsb", ".dsz", ".emd",
    ".emb",
    ".exy", ".fxy", ".gt", ".hus", ".inb", ".jpx", ".ksm",
    ".max", ".mit", ".new", ".pcd", ".pcm", ".pcq", ".pcs",
    ".phb", ".phc", ".sew", ".shv", ".stc", ".stx", ".tap",
    ".zhs", ".zxy", ".csv", ".json",
]


def _normalize_ext(ext: str) -> str:
    """Return extension with leading dot, lowercase."""
    ext = (ext or "").strip().lower()
    if ext and not ext.startswith("."):
        ext = "." + ext
    return ext


def is_readable_format(ext: str) -> bool:
    return _normalize_ext(ext) in READABLE_EXTENSIONS


def is_writable_format(ext: str) -> bool:
    return _normalize_ext(ext) in WRITABLE_EXTENSIONS


def convert_embroidery(source_bytes: bytes, source_ext: str, target_ext: str) -> bytes:
    """
    Convert embroidery data from one format to another.
    Raises ValueError for unsupported format or on read/write errors.
    """
    src_ext = _normalize_ext(source_ext)
    tgt_ext = _normalize_ext(target_ext)

    if not is_readable_format(src_ext):
        raise ValueError(f"Unsupported source format: {source_ext}")
    if not is_writable_format(tgt_ext):
        raise ValueError(f"Unsupported target format: {target_ext}")

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "src" + src_ext)
        out_path = os.path.join(tmpdir, "out" + tgt_ext)

        with open(src_path, "wb") as f:
            f.write(source_bytes)

        try:
            pattern = pyembroidery.read(src_path)
        except Exception as e:
            logger.warning("pyembroidery read failed: %s", e)
            raise ValueError(f"Cannot read file as {src_ext}: {e}") from e

        if pattern is None:
            raise ValueError(f"Failed to parse file as {src_ext}")

        stitches = list(pattern.stitches) if pattern.stitches else []
        if not stitches:
            raise ValueError(f"File has no stitches; cannot convert")

        # Writer settings for better machine compatibility (tie-on/tie-off at color changes)
        write_settings = {
            "tie_on": pyembroidery.CONTINGENCY_TIE_ON_THREE_SMALL,
            "tie_off": pyembroidery.CONTINGENCY_TIE_OFF_THREE_SMALL,
        }

        try:
            pyembroidery.write(pattern, out_path, write_settings)
        except Exception as e:
            logger.warning("pyembroidery write failed: %s", e)
            raise ValueError(f"Cannot write format {tgt_ext}: {e}") from e

        with open(out_path, "rb") as f:
            return f.read()
