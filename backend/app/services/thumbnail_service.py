import logging
import os
import io
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, List, Tuple

import pyembroidery
from PIL import Image, ImageDraw

from app.services.smb_service import SMBService

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (200, 200)
PREVIEW_SIZE = (600, 600)

# Image and document types that get thumbnails/previews (not embroidery)
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
PDF_EXTENSIONS = {'.pdf'}

THREAD_COLORS = {
    'default': '#333333',
    'jump': '#aaaaaa',
}

DEFAULT_PALETTE = [
    '#000000', '#ffffff', '#ff0000', '#00ff00', '#0000ff', '#ffff00',
    '#ff00ff', '#00ffff', '#ff8800', '#88ff00', '#0088ff', '#ff0088',
    '#8800ff', '#00ff88', '#888888', '#ffaaaa', '#aaffaa', '#aaaaff',
]


class ThumbnailService:
    def __init__(self, smb_service: SMBService):
        self.smb = smb_service
    
    def _get_cache_path(self, file_path: str, size: Tuple[int, int] = THUMBNAIL_SIZE) -> str:
        """Get cache path for thumbnail"""
        cache_dir = os.environ.get("THUMBNAIL_CACHE_DIR", "/app/data/thumbnails")
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        size_str = f"{size[0]}x{size[1]}"
        return os.path.join(cache_dir, f"{file_hash}_{size_str}.png")
    
    async def get_thumbnail(self, file_path: str, size: Tuple[int, int] = THUMBNAIL_SIZE) -> bytes:
        """Get or generate thumbnail for an embroidery file"""
        cache_path = self._get_cache_path(file_path, size)
        
        if os.path.exists(cache_path):
            with open(cache_path, 'rb') as f:
                return f.read()
        
        thumbnail = await self._generate_thumbnail(file_path, size)
        
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'wb') as f:
            f.write(thumbnail)
        
        return thumbnail
    
    async def _generate_thumbnail(self, file_path: str, size: Tuple[int, int]) -> bytes:
        """Generate thumbnail for embroidery, image, or PDF file"""
        file_data = self.smb.get_file(file_path)
        ext = Path(file_path).suffix.lower()

        if ext in IMAGE_EXTENSIONS:
            return self._render_image_thumbnail(file_data, size, ext)
        if ext in PDF_EXTENSIONS:
            return self._render_pdf_thumbnail(file_data, size)

        # Embroidery formats (including .emb for Embroidery by TM)
        if ext in ['.dst', '.pes']:
            return await self._render_embroidery_thumbnail(file_data, size, ext.lstrip('.'))
        if ext in ['.pec', '.exp', '.vp3', '.jef', '.xxx', '.sew', '.dsz', '.tap', '.hus', '.pcs', '.emb']:
            return await self._render_embroidery_thumbnail(file_data, size, ext.lstrip('.'))
        if ext == '.vip':
            return self._render_placeholder_thumbnail(ext, size)
        return self._render_placeholder_thumbnail(ext, size)
    
    def _render_image_thumbnail(self, data: bytes, size: Tuple[int, int], ext: str) -> bytes:
        """Render thumbnail from image file (jpg, png, etc.)"""
        try:
            img = Image.open(io.BytesIO(data))
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail(size, Image.Resampling.LANCZOS)
            out = Image.new('RGB', size, color='#ffffff')
            paste_x = (size[0] - img.width) // 2
            paste_y = (size[1] - img.height) // 2
            out.paste(img, (paste_x, paste_y))
            return self._image_to_bytes(out, size)
        except Exception as e:
            logger.warning("Image thumbnail failed: %s", e)
            return self._render_placeholder_thumbnail(ext, size)

    def _render_pdf_thumbnail(self, data: bytes, size: Tuple[int, int]) -> bytes:
        """Render first page of PDF as thumbnail"""
        try:
            import pymupdf
            doc = pymupdf.open(stream=data, filetype="pdf")
            if doc.page_count == 0:
                doc.close()
                return self._render_placeholder_thumbnail('.pdf', size)
            page = doc[0]
            zoom = min(size[0] / page.rect.width, size[1] / page.rect.height)
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            if img.size != size:
                img = img.resize(size, Image.Resampling.LANCZOS)
            return self._image_to_bytes(img, size)
        except Exception as e:
            logger.warning("PDF thumbnail failed: %s", e)
            return self._render_placeholder_thumbnail('.pdf', size)

    async def _render_embroidery_thumbnail(self, data: bytes, size: Tuple[int, int], fmt: str) -> bytes:
        """Render thumbnail from embroidery file using pyembroidery"""
        import tempfile
        try:
            # Write to temp file - pyembroidery needs a file path
            suffix = fmt if fmt.startswith('.') else '.' + fmt
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(data)
                temp_path = f.name
            
            try:
                pattern = pyembroidery.read(temp_path)
                
                if pattern is None:
                    return self._render_placeholder_thumbnail(f".{fmt}", size)
                    
                result = self._render_pattern(pattern, size)
                logger.info(f"Successfully rendered {fmt} pattern, size={len(result)}")
                return result
            finally:
                os.unlink(temp_path)
        except Exception as e:
            logger.error(f"Error rendering {fmt}: {e}")
            return self._render_placeholder_thumbnail(f".{fmt}", size)
    
    def _render_pattern(self, pattern: 'pyembroidery.EmbPattern', size: Tuple[int, int]) -> bytes:
        """Render an embroidery pattern to an image"""
        import pyembroidery
        
        stitches = list(pattern.stitches)
        if not stitches:
            return self._render_placeholder_thumbnail('empty', size)
        
        min_x = min(s[0] for s in stitches)
        max_x = max(s[0] for s in stitches)
        min_y = min(s[1] for s in stitches)
        max_y = max(s[1] for s in stitches)
        
        pattern_width = max_x - min_x or 1
        pattern_height = max_y - min_y or 1
        
        padding = 20
        available_width = size[0] - padding * 2
        available_height = size[1] - padding * 2
        
        scale = min(available_width / pattern_width, available_height / pattern_height)
        
        offset_x = (size[0] - pattern_width * scale) / 2 - min_x * scale
        offset_y = (size[1] - pattern_height * scale) / 2 - min_y * scale
        
        img = Image.new('RGB', size, color='#ffffff')
        draw = ImageDraw.Draw(img)
        
        threads = pattern.threadlist if hasattr(pattern, 'threadlist') and pattern.threadlist else []
        
        current_color_idx = 0
        current_color = self._get_thread_color(threads, 0) if threads else DEFAULT_PALETTE[0]
        
        prev_x = None
        prev_y = None
        
        for i, stitch in enumerate(stitches):
            command = stitch[2] if len(stitch) > 2 else pyembroidery.STITCH
            x = stitch[0] * scale + offset_x
            y = stitch[1] * scale + offset_y
            
            # Handle color changes - command 5 is COLOR_CHANGE
            if command == pyembroidery.COLOR_CHANGE:
                if len(stitch) > 3:
                    current_color_idx = stitch[3]
                current_color = self._get_thread_color(threads, current_color_idx)
                prev_x, prev_y = None, None
                continue
            
            # Skip jumps (command 1) or end markers (command 4)
            if command == pyembroidery.JUMP or command == pyembroidery.END:
                prev_x, prev_y = None, None
                continue
            
            if prev_x is not None:
                draw.line([(prev_x, prev_y), (x, y)], fill=current_color, width=2)
            
            prev_x = x
            prev_y = y
        
        return self._image_to_bytes(img, size)
    
    def _get_thread_color(self, threads: list, idx: int) -> str:
        """Get color from thread list or use default"""
        if threads and idx < len(threads):
            thread = threads[idx]
            try:
                r = thread.get_red()
                g = thread.get_green()
                b = thread.get_blue()
                return self._rgb_to_hex((r, g, b))
            except Exception:
                pass
        return DEFAULT_PALETTE[idx % len(DEFAULT_PALETTE)]
    
    def _rgb_to_hex(self, rgb: Tuple[int, int, int]) -> str:
        """Convert RGB tuple to hex color"""
        return '#{:02x}{:02x}{:02x}'.format(
            min(255, max(0, rgb[0])),
            min(255, max(0, rgb[1])),
            min(255, max(0, rgb[2]))
        )
    
    def _render_placeholder_thumbnail(self, ext: str, size: Tuple[int, int]) -> bytes:
        """Render placeholder thumbnail for unknown formats"""
        img = Image.new('RGB', size, color='#e0e0e0')
        draw = ImageDraw.Draw(img)
        
        ext_upper = ext.upper().replace('.', '')
        center_x = size[0] // 2
        center_y = size[1] // 2
        
        draw.ellipse([
            center_x - 40, center_y - 40,
            center_x + 40, center_y + 40
        ], outline='#888888', width=2)
        draw.text((center_x, center_y), ext_upper, fill='#666666', anchor='mm')
        
        return self._image_to_bytes(img, size)
    
    def _image_to_bytes(self, img: 'Image.Image', size: Tuple[int, int]) -> bytes:
        """Convert PIL Image to bytes"""
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
