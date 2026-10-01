"""What each hotkey does. The UI and the hotkey layer only call ``handle_action``.

Threading model:
* All public methods and signals run on the UI thread.
* Slow work (screenshot + OCR, screenshot + save) runs on single-thread
  executors, so the UI never freezes and results arrive in order.
* Results come back through private Qt signals, which Qt delivers on the UI
  thread; clipboard and the new-text tracker are only touched there.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QObject, QTimer, Signal

from . import clipboard, config
from .config import HotkeyAction
from .geometry import Point, ScreenRect
from .image_output import mask_outside_polygon, save_image
from .ocr_engine import OcrError, TextRecognizer, WindowsOcrRecognizer
from .paths import resolve_user_path
from .point_picker import PickMode
from .region_selector import RegionSelector
from .screen_capture import CaptureError, grab_region
from .settings import AppSettings, ImageCaptureSettings, OcrSettings
from .silent_selector import SilentSelector
from .text_diff import NewTextTracker
from .text_layout import LayoutOptions, build_text
from .win32.mouse_hook import MouseHookError

log = logging.getLogger(__name__)

# Errors whose message is written for the user; anything else is a bug.
_EXPECTED_ERRORS = (OcrError, CaptureError, MouseHookError, OSError)

_PICK_INSTRUCTIONS = {
    PickMode.RECTANGLE: "Image: click the START point, then the END point. Right click cancels.",
    PickMode.FREEFORM: "Freeform: click the START point, move along the shape, click again to close it. "
    "Right click cancels.",
}
_FILE_PREFIXES = {
    PickMode.RECTANGLE: config.IMAGE_FILE_PREFIX_RECTANGLE,
    PickMode.FREEFORM: config.IMAGE_FILE_PREFIX_FREEFORM,
}

RecognizerFactory = Callable[[OcrSettings], TextRecognizer]
Grabber = Callable[[ScreenRect], Image.Image]


def _default_recognizer_factory(ocr: OcrSettings) -> TextRecognizer:
    return WindowsOcrRecognizer(ocr.language, ocr.upscale_factor)


@dataclass(frozen=True)
class _ImageResult:
    image: Image.Image
    path: Path


class CaptureController(QObject):
    status = Signal(str, bool)  # message, is_error
    text_captured = Signal(str)  # only the new text
    region_selected = Signal(object)  # ScreenRect

    _text_job_done = Signal(object)  # str | Exception
    _image_job_done = Signal(object)  # _ImageResult | Exception

    def __init__(
        self,
        get_settings: Callable[[], AppSettings],
        recognizer_factory: RecognizerFactory = _default_recognizer_factory,
        grab: Grabber = grab_region,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_settings = get_settings
        self._recognizer_factory = recognizer_factory
        self._grab = grab
        self._recognizer: TextRecognizer | None = None
        self._recognizer_settings: OcrSettings | None = None

        self._tracker = NewTextTracker()
        self._text_busy = False
        self._text_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")
        self._image_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="image")

        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._capture_text_once)

        self._region_selector = RegionSelector(self)
        self._region_selector.selected.connect(self._on_region_selected)
        self._region_selector.cancelled.connect(lambda reason: self.status.emit(reason, False))

        self._silent_selector = SilentSelector(self)
        self._silent_selector.completed.connect(self._on_points_picked)
        self._silent_selector.cancelled.connect(lambda reason: self.status.emit(reason, False))

        self._text_job_done.connect(self._on_text_job_done)
        self._image_job_done.connect(self._on_image_job_done)

        self._handlers: dict[HotkeyAction, Callable[[], None]] = {
            HotkeyAction.SET_REGION: self.set_region,
            HotkeyAction.CAPTURE_NEW_TEXT: self.capture_new_text,
            HotkeyAction.CAPTURE_IMAGE: lambda: self._toggle_silent_pick(PickMode.RECTANGLE),
            HotkeyAction.CAPTURE_FREEFORM_IMAGE: lambda: self._toggle_silent_pick(PickMode.FREEFORM),
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def handle_action(self, action_id: str) -> None:
        try:
            handler = self._handlers[HotkeyAction(action_id)]
        except (ValueError, KeyError):
            log.error("No handler for hotkey action %r", action_id)
            return
        log.debug("Hotkey action: %s", action_id)
        handler()

    def set_region(self) -> None:
        """set_region hotkey: show the drag overlay."""
        self._silent_selector.cancel("Replaced by region selection.")
        self._region_selector.start()
        self.status.emit("Drag over the text area. Esc or right click cancels.", False)

    def capture_new_text(self) -> None:
        """capture_new_text hotkey: one capture, or toggle live captioning."""
        interval = self._get_settings().text_capture.live_caption_interval_ms
        if self._live_timer.isActive():
            self._live_timer.stop()
            self.status.emit("Live captioning stopped.", False)
            return
        if interval > 0 and self._get_settings().region is not None:
            self._live_timer.start(interval)
            self.status.emit(f"Live captioning every {interval} ms. Press the hotkey again to stop.", False)
        self._capture_text_once()

    def reset_text_memory(self) -> None:
        """Forget the last capture, so the next capture returns all text."""
        self._tracker.reset()

    def stop_all(self) -> None:
        """Cancel everything in progress (used when hotkeys are stopped)."""
        self._live_timer.stop()
        self._region_selector.cancel()
        self._silent_selector.cancel("Stopped.")

    def shutdown(self) -> None:
        self.stop_all()
        self._text_executor.shutdown(wait=False, cancel_futures=True)
        self._image_executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ #
    # Region
    # ------------------------------------------------------------------ #
    def _on_region_selected(self, rect: ScreenRect) -> None:
        self._tracker.reset()
        self.region_selected.emit(rect)
        self.status.emit(f"Region set: {rect}", False)

    # ------------------------------------------------------------------ #
    # Text capture
    # ------------------------------------------------------------------ #
    def _capture_text_once(self) -> None:
        settings = self._get_settings()
        if settings.region is None:
            self._live_timer.stop()
            self.status.emit("No region yet. Press the set_region hotkey first.", True)
            return
        if self._text_busy:
            log.debug("OCR still running; capture skipped")
            return
        self._text_busy = True
        layout = LayoutOptions(preserve_layout=settings.text_capture.preserve_layout)
        self._text_executor.submit(self._run_text_job, settings.region, self._recognizer_for(settings.ocr), layout)

    def _recognizer_for(self, ocr: OcrSettings) -> TextRecognizer:
        if self._recognizer is None or self._recognizer_settings != ocr:
            self._recognizer = self._recognizer_factory(ocr)
            self._recognizer_settings = ocr
        return self._recognizer

    def _run_text_job(self, region: ScreenRect, recognizer: TextRecognizer, layout: LayoutOptions) -> None:
        """Worker thread."""
        try:
            lines = recognizer.recognize(self._grab(region))
            result: str | Exception = build_text(lines, layout)
        except Exception as exc:
            if not isinstance(exc, _EXPECTED_ERRORS):
                log.exception("Text capture failed")
            result = exc
        self._text_job_done.emit(result)

    def _on_text_job_done(self, result: str | Exception) -> None:
        self._text_busy = False
        if isinstance(result, Exception):
            self._live_timer.stop()
            self.status.emit(self._describe_error("Text capture failed", result), True)
            return

        text_settings = self._get_settings().text_capture
        self._tracker.similarity_threshold = text_settings.similarity_threshold
        new_text = self._tracker.update(result)
        if not new_text:
            if not self._live_timer.isActive():
                self.status.emit("No new text.", False)
            return

        if text_settings.copy_to_clipboard:
            clipboard.copy_text(new_text)
        if text_settings.transcript_file:
            self._append_transcript(text_settings.transcript_file, new_text)
        self.text_captured.emit(new_text)

    def _append_transcript(self, file_text: str, new_text: str) -> None:
        path = resolve_user_path(file_text)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding=config.TRANSCRIPT_ENCODING) as handle:
                handle.write(new_text + "\n")
        except OSError as exc:
            self.status.emit(f"Could not write transcript {path}: {exc}", True)

    # ------------------------------------------------------------------ #
    # Silent image capture
    # ------------------------------------------------------------------ #
    def _toggle_silent_pick(self, mode: PickMode) -> None:
        """Pressing the same image hotkey again cancels the selection."""
        if self._silent_selector.active_mode is mode:
            self._silent_selector.cancel("Selection cancelled (hotkey pressed again).")
            return
        selection = self._get_settings().selection
        try:
            self._silent_selector.start(mode, selection.timeout_seconds, selection.freeform_min_point_distance_px)
        except MouseHookError as exc:
            self.status.emit(str(exc), True)
            return
        self.status.emit(_PICK_INSTRUCTIONS[mode], False)

    def _on_points_picked(self, mode: PickMode, points: list[Point]) -> None:
        if mode is PickMode.FREEFORM and len(points) < config.MIN_FREEFORM_POINTS:
            self.status.emit("Freeform shape needs more points. Move the mouse between the two clicks.", True)
            return
        rect = ScreenRect.bounding(points)
        if not rect.is_at_least(config.MIN_CAPTURE_SIZE_PX):
            self.status.emit(f"Area too small (minimum {config.MIN_CAPTURE_SIZE_PX} px).", True)
            return
        self._image_executor.submit(self._run_image_job, mode, points, rect, self._get_settings().image_capture)

    def _run_image_job(
        self, mode: PickMode, points: list[Point], rect: ScreenRect, image_settings: ImageCaptureSettings
    ) -> None:
        """Worker thread."""
        try:
            image = self._grab(rect)
            if mode is PickMode.FREEFORM:
                image = mask_outside_polygon(image, points, rect.origin)
            path = save_image(
                image,
                resolve_user_path(image_settings.output_folder),
                _FILE_PREFIXES[mode],
                image_settings.file_format,
                image_settings.background_color,
            )
            result: _ImageResult | Exception = _ImageResult(image, path)
        except Exception as exc:
            if not isinstance(exc, _EXPECTED_ERRORS):
                log.exception("Image capture failed")
            result = exc
        self._image_job_done.emit(result)

    def _on_image_job_done(self, result: _ImageResult | Exception) -> None:
        if isinstance(result, Exception):
            self.status.emit(self._describe_error("Image capture failed", result), True)
            return
        image_settings = self._get_settings().image_capture
        if image_settings.copy_to_clipboard:
            clipboard.copy_image(result.image, image_settings.background_color)
        log.info("Image saved: %s", result.path)
        self.status.emit(f"Image saved: {result.path}", False)

    @staticmethod
    def _describe_error(prefix: str, exc: Exception) -> str:
        if isinstance(exc, _EXPECTED_ERRORS):
            return f"{prefix}: {exc}"
        return f"{prefix}: unexpected error ({type(exc).__name__}: {exc}). See the log file."
