"""Silent screenshots of a screen rectangle.

Uses ``mss`` (GDI BitBlt): nothing is drawn on screen, the cursor is not
included and the cursor shape is not changed. Works across multiple monitors,
including monitors left of / above the main one (negative coordinates).
"""

from __future__ import annotations

import mss
from PIL import Image

from .geometry import ScreenRect


class CaptureError(RuntimeError):
    """The screenshot failed. The message is user-facing."""


def grab_region(rect: ScreenRect) -> Image.Image:
    """Return an RGB image of ``rect``. Safe to call from any thread."""
    monitor = {"left": rect.left, "top": rect.top, "width": rect.width, "height": rect.height}
    try:
        # A new MSS instance per call: instances must not be shared between threads.
        with mss.MSS() as screen:
            shot = screen.grab(monitor)
    except mss.ScreenShotError as exc:
        raise CaptureError(f"Screenshot failed for {rect}: {exc}") from exc
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
