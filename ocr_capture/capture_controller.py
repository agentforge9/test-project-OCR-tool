"""What each hotkey does. The UI and the hotkey layer only call ``handle_action``.

Text flow (live captions or any other text):
1. ``activate`` (on Start) and every new region reset the tracker.
2. While active, the region is read in the background every
   ``poll_interval_ms``. The first read puts all visible words in the
   tracker's buffer; later reads add only the words that appeared since.
3. The capture_new_text hotkey requests one fresh read, then *delivers* the
   buffer: clipboard + Ctrl+V into the focused box + history. So the first
   press pastes all text in the region, later presses only what is new.
   An empty buffer delivers nothing (clipboard untouched).

Threading model:
* All public methods and signals run on the UI thread.
* Slow work (screenshot + OCR, screenshot + save) runs on single-thread
  executors, so the UI never freezes and results arrive in order.
* Results come back through private Qt signals, which Qt delivers on the UI
  thread; clipboard and the caption tracker are only touched there.
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
from .auto_paster import AutoPaster
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
from .text_diff import CaptionTracker
from .text_layout import OcrLine
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


def _words_in_reading_order(lines: list[OcrLine]) -> list[str]:
    filled = [line for line in lines if line.words]
    return [word.text for line in sorted(filled, key=lambda ln: ln.top) for word in line.words]


@dataclass(frozen=True)
class _TextResult:
    words: list[str] | None
    error: Exception | None
    deliver: bool
    generation: int  # results from before the last tracker reset are ignored


@dataclass(frozen=True)
class _ImageResult:
    image: Image.Image
    path: Path


class CaptureController(QObject):
    status = Signal(str, bool)  # message, is_error
    text_delivered = Signal(str)  # new caption words handed to the user
    region_selected = Signal(object)  # ScreenRect

    _text_job_done = Signal(object)  # _TextResult
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

        self._active = False
        self._tracker = CaptionTracker()
        self._generation = 0
        self._read_busy = False
        self._delivery_requested = False
        self._delivered_since_reset = False
        self._text_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")
        self._image_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="image")

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(lambda: self._request_read(deliver=False))

        self._paster = AutoPaster(self)
        self._paster.failed.connect(lambda reason: self.status.emit(reason, True))

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

    def activate(self) -> None:
        """Hotkeys are on: start watching the caption region."""
        self._active = True
        self._restart_watching()

    def stop_all(self) -> None:
        """Hotkeys are off: stop watching and cancel everything in progress."""
        self._active = False
        self._poll_timer.stop()
        self._paster.cancel()
        self._region_selector.cancel()
        self._silent_selector.cancel("Stopped.")
        self._reset_tracker()
        self._delivery_requested = False

    def shutdown(self) -> None:
        self.stop_all()
        self._text_executor.shutdown(wait=False, cancel_futures=True)
        self._image_executor.shutdown(wait=False, cancel_futures=True)

    def set_region(self) -> None:
        """set_region hotkey: show the drag overlay."""
        self._silent_selector.cancel("Replaced by region selection.")
        self._region_selector.start()
        self.status.emit("Drag over the caption area. Esc or right click cancels.", False)

    def capture_new_text(self) -> None:
        """capture_new_text hotkey: read once more, then deliver the new words."""
        if self._get_settings().region is None:
            self.status.emit("No region yet. Press the set_region hotkey first.", True)
            return
        self._request_read(deliver=True)

    # ------------------------------------------------------------------ #
    # Caption watching
    # ------------------------------------------------------------------ #
    def _on_region_selected(self, rect: ScreenRect) -> None:
        self.region_selected.emit(rect)  # app.py stores it in the settings first
        self._restart_watching()
        self.status.emit(f"Region set: {rect}. Click a text box and press the paste hotkey.", False)

    def _restart_watching(self) -> None:
        """Reset the tracker and read the region right away."""
        self._reset_tracker()
        self._poll_timer.stop()
        settings = self._get_settings()
        if not self._active or settings.region is None:
            return
        interval = settings.text_capture.poll_interval_ms
        if interval > 0:
            self._poll_timer.start(interval)
        self._request_read(deliver=False)

    def _reset_tracker(self) -> None:
        self._tracker.reset()
        self._generation += 1
        self._delivered_since_reset = False

    def _request_read(self, deliver: bool) -> None:
        """Read the region on the OCR thread. ``deliver`` = hand out new words after."""
        if deliver:
            self._delivery_requested = True
        if self._read_busy:
            return  # a delivery request is picked up when the running read ends
        region = self._get_settings().region
        if region is None:
            return
        self._read_busy = True
        deliver_now, self._delivery_requested = self._delivery_requested, False
        recognizer = self._recognizer_for(self._get_settings().ocr)
        self._text_executor.submit(self._run_text_job, region, recognizer, deliver_now, self._generation)

    def _recognizer_for(self, ocr: OcrSettings) -> TextRecognizer:
        if self._recognizer is None or self._recognizer_settings != ocr:
            self._recognizer = self._recognizer_factory(ocr)
            self._recognizer_settings = ocr
        return self._recognizer

    def _run_text_job(self, region: ScreenRect, recognizer: TextRecognizer, deliver: bool, generation: int) -> None:
        """Worker thread."""
        try:
            words = _words_in_reading_order(recognizer.recognize(self._grab(region)))
            result = _TextResult(words, None, deliver, generation)
        except Exception as exc:
            level = logging.WARNING if isinstance(exc, _EXPECTED_ERRORS) else logging.ERROR
            log.log(level, "Text read failed", exc_info=exc)
            result = _TextResult(None, exc, deliver, generation)
        self._text_job_done.emit(result)

    def _on_text_job_done(self, result: _TextResult) -> None:
        self._read_busy = False
        if result.generation != self._generation:
            # Read of an old region/session: take a fresh read instead.
            if self._active:
                self._request_read(deliver=result.deliver or self._delivery_requested)
            return
        if result.error is not None:
            self._poll_timer.stop()
            self.status.emit(self._describe_error("Reading the region failed", result.error), True)
        elif self._active or result.deliver:
            self._tracker.observe(result.words or [])
            if result.deliver:
                self._deliver(found_any_text=bool(result.words))

        if self._delivery_requested:
            self._request_read(deliver=True)

    def _deliver(self, found_any_text: bool) -> None:
        text = self._tracker.take_pending()
        if not text:
            message = (
                "No new text since the last paste. Nothing pasted."
                if found_any_text
                else "No text found in the region. Nothing pasted. Check the region covers the text."
            )
            self.status.emit(message, False)
            return

        text_settings = self._get_settings().text_capture
        if text_settings.auto_paste:
            separator = text_settings.paste_separator if self._delivered_since_reset else ""
            clipboard.copy_text(separator + text)
            self._paster.paste_clipboard()
        elif text_settings.copy_to_clipboard:
            clipboard.copy_text(text)
        self._delivered_since_reset = True

        if text_settings.transcript_file:
            self._append_transcript(text_settings.transcript_file, text)
        self.text_delivered.emit(text)
        self.status.emit(f"New text: {len(text.split())} words.", False)

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
