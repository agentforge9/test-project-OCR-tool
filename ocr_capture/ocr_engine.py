"""Text recognition with the OCR engine built into Windows 10/11.

Why Windows OCR: it ships with Windows, so the exe needs no extra install
(no Tesseract, no model files) and works on any Windows PC that has the
OCR language pack for the language you read.

The rest of the app only depends on the small ``TextRecognizer`` protocol,
so another engine (e.g. Tesseract) can be plugged in without other changes.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Protocol

from PIL import Image

from .text_layout import OcrLine, OcrWord

log = logging.getLogger(__name__)

_RESAMPLE = Image.Resampling.BICUBIC


class OcrError(RuntimeError):
    """OCR could not run. The message is user-facing."""


class TextRecognizer(Protocol):
    def recognize(self, image: Image.Image) -> list[OcrLine]:
        """Return recognized lines with word boxes in ``image`` pixel units."""
        ...


class WindowsOcrRecognizer:
    """``TextRecognizer`` backed by ``Windows.Media.Ocr``.

    The engine is created lazily on first use, in the calling (worker)
    thread. A lock makes concurrent calls safe, although the app only ever
    calls it from one worker thread.
    """

    def __init__(self, language_tag: str, upscale_factor: float) -> None:
        self._language_tag = language_tag.strip()
        self._upscale_factor = upscale_factor
        self._engine = None
        self._lock = threading.Lock()

    def recognize(self, image: Image.Image) -> list[OcrLine]:
        with self._lock:
            engine = self._get_engine()
            scaled, scale = self._scale_for_ocr(image, engine)
            bitmap = self._to_software_bitmap(scaled)
            result = asyncio.run(self._recognize_async(engine, bitmap))
        return [
            OcrLine(
                tuple(
                    OcrWord(
                        text=word.text,
                        left=word.bounding_rect.x / scale,
                        top=word.bounding_rect.y / scale,
                        width=word.bounding_rect.width / scale,
                        height=word.bounding_rect.height / scale,
                    )
                    for word in line.words
                )
            )
            for line in result.lines
        ]

    @staticmethod
    async def _recognize_async(engine, bitmap):
        return await engine.recognize_async(bitmap)

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        from winrt.windows.globalization import Language
        from winrt.windows.media.ocr import OcrEngine

        available = ", ".join(lang.language_tag for lang in OcrEngine.available_recognizer_languages) or "none"
        if self._language_tag:
            language = Language(self._language_tag)
            if not OcrEngine.is_language_supported(language):
                raise OcrError(
                    f"OCR language '{self._language_tag}' is not installed. Installed: {available}. "
                    f"Add it in Windows Settings > Time & language > Language, or change "
                    f"'ocr.language' in settings.json."
                )
            engine = OcrEngine.try_create_from_language(language)
        else:
            engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise OcrError(f"Windows OCR is not available for your languages. Installed OCR languages: {available}.")
        log.info("Windows OCR ready (language %s)", engine.recognizer_language.language_tag)
        self._engine = engine
        return engine

    def _scale_for_ocr(self, image: Image.Image, engine) -> tuple[Image.Image, float]:
        """Enlarge small text for better accuracy, within the engine size limit."""
        from winrt.windows.media.ocr import OcrEngine

        max_side = OcrEngine.max_image_dimension
        scale = min(self._upscale_factor, max_side / max(image.width, image.height))
        if abs(scale - 1.0) < 1e-3:
            return image, 1.0
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        return image.resize(size, _RESAMPLE), scale

    @staticmethod
    def _to_software_bitmap(image: Image.Image):
        from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap

        rgba = image.convert("RGBA")
        return SoftwareBitmap.create_copy_from_buffer(
            rgba.tobytes("raw", "BGRA"), BitmapPixelFormat.BGRA8, rgba.width, rgba.height
        )
