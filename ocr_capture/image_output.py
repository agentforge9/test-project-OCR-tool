"""Image post-processing and saving (no Qt here, so it is testable)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw

from . import config
from .geometry import Point

_OPAQUE = 255
_FORMATS_WITH_ALPHA = frozenset({"png"})
_PIL_FORMAT_NAMES = {"png": "PNG", "jpg": "JPEG", "bmp": "BMP"}


def mask_outside_polygon(image: Image.Image, polygon: Sequence[Point], origin: Point) -> Image.Image:
    """Make everything outside ``polygon`` transparent.

    ``polygon`` is in screen coordinates; ``origin`` is the screen position
    of the image's top-left pixel. The polygon is closed automatically
    (last point connects back to the first).
    """
    mask = Image.new("L", image.size, 0)
    local = [(p.x - origin.x, p.y - origin.y) for p in polygon]
    ImageDraw.Draw(mask).polygon(local, fill=_OPAQUE, outline=_OPAQUE)
    result = image.convert("RGBA")
    result.putalpha(mask)
    return result


def flatten_alpha(image: Image.Image, background: str) -> Image.Image:
    """Put a transparent image on a solid colour (for clipboard, jpg, bmp)."""
    if image.mode != "RGBA":
        return image.convert("RGB")
    base = Image.new("RGBA", image.size, ImageColor.getrgb(background) + (_OPAQUE,))
    return Image.alpha_composite(base, image).convert("RGB")


def build_file_name(prefix: str, file_format: str, now: datetime | None = None) -> str:
    stamp = (now or datetime.now()).strftime(config.IMAGE_TIMESTAMP_FORMAT)
    return f"{prefix}_{stamp}.{file_format.lower()}"


def save_image(image: Image.Image, folder: Path, prefix: str, file_format: str, background: str) -> Path:
    """Save with a unique timestamped name and return the file path."""
    file_format = file_format.lower()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / build_file_name(prefix, file_format)

    to_save = image if file_format in _FORMATS_WITH_ALPHA else flatten_alpha(image, background)
    options = {"quality": config.JPEG_QUALITY} if file_format == "jpg" else {}
    to_save.save(path, _PIL_FORMAT_NAMES[file_format], **options)
    return path
