"""Clipboard helpers. Must be called on the UI thread (Qt requirement)."""

from __future__ import annotations

from PIL import Image
from PySide6.QtGui import QGuiApplication, QImage

from .image_output import flatten_alpha

_RGB_BYTES_PER_PIXEL = 3


def copy_text(text: str) -> None:
    QGuiApplication.clipboard().setText(text)


def copy_image(image: Image.Image, background: str) -> None:
    """Copy an image; transparency is filled with ``background`` because most
    programs ignore clipboard transparency and would show black instead."""
    rgb = flatten_alpha(image, background)
    data = rgb.tobytes("raw", "RGB")
    qimage = QImage(data, rgb.width, rgb.height, rgb.width * _RGB_BYTES_PER_PIXEL, QImage.Format.Format_RGB888)
    # copy(): QImage does not own ``data``; the copy does.
    QGuiApplication.clipboard().setImage(qimage.copy())
