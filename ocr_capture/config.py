"""Every tunable value of the app lives in this file.

Rule of thumb:
* Values a user may want to change at run time are *defaults* here and are
  copied into ``settings.json`` (next to the exe) on first start.
  ``settings.json`` always wins over the defaults below.
* Values that only a developer should touch (timings, colours, limits) are
  plain constants here and are not written to ``settings.json``.

Change a value here once and the whole app picks it up; no logic file
contains its own magic numbers.
"""

from __future__ import annotations

from enum import StrEnum

# --------------------------------------------------------------------------- #
# App identity and files (all files are stored next to the exe)
# --------------------------------------------------------------------------- #
APP_NAME = "OCR Region Capture"
APP_EXE_NAME = "OcrRegionCapture"
SETTINGS_FILE_NAME = "settings.json"
LOG_FILE_NAME = "ocr_region_capture.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 2
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


# --------------------------------------------------------------------------- #
# Hotkey actions
# --------------------------------------------------------------------------- #
class HotkeyAction(StrEnum):
    """Every action that can be bound to a global hotkey.

    The string value is the key used in ``settings.json``. To add a new
    action: add a member here, give it a default hotkey and a label below,
    and add a handler in ``CaptureController._handlers``.
    """

    SET_REGION = "set_region"
    CAPTURE_NEW_TEXT = "capture_new_text"
    CAPTURE_IMAGE = "capture_image"
    CAPTURE_FREEFORM_IMAGE = "capture_freeform_image"


# DEFAULT HOTKEYS ----------------------------------------------------------- #
# These are used when settings.json is missing, or when it has no (or an
# invalid) entry for an action. The hotkeys the app really uses are in
# settings.json -> "hotkeys". Format: modifiers + key joined by "+",
# e.g. "Ctrl+Alt+F9". See hotkey_spec.py for every supported key name.
DEFAULT_HOTKEYS: dict[HotkeyAction, str] = {
    HotkeyAction.SET_REGION: "Alt+Comma",
    HotkeyAction.CAPTURE_NEW_TEXT: "Alt+Period",
    HotkeyAction.CAPTURE_IMAGE: "Alt+Slash",
    HotkeyAction.CAPTURE_FREEFORM_IMAGE: "Alt+Shift+Slash",
}

ACTION_LABELS: dict[HotkeyAction, str] = {
    HotkeyAction.SET_REGION: "set_region_hotkey:",
    HotkeyAction.CAPTURE_NEW_TEXT: "capture_new_text_hotkey:",
    HotkeyAction.CAPTURE_IMAGE: "capture_image_hotkey:",
    HotkeyAction.CAPTURE_FREEFORM_IMAGE: "capture_freeform_image_hotkey:",
}

ACTION_TOOLTIPS: dict[HotkeyAction, str] = {
    HotkeyAction.SET_REGION: "Drag with the mouse to choose the text region.",
    HotkeyAction.CAPTURE_NEW_TEXT: "Read the text in the region and output only what is new.",
    HotkeyAction.CAPTURE_IMAGE: "Click a start point, then an end point. The rectangle is saved silently.",
    HotkeyAction.CAPTURE_FREEFORM_IMAGE: (
        "Click a start point, move the mouse along any path, click again. "
        "The closed shape is saved silently."
    ),
}

# Win32 hotkey ids must be in 0x0000..0xBFFF; ours start here.
HOTKEY_ID_BASE = 0x1000
# True = holding a hotkey down fires it once, not repeatedly.
HOTKEY_SUPPRESS_AUTOREPEAT = True

# --------------------------------------------------------------------------- #
# OCR (defaults, user-editable in settings.json -> "ocr")
# --------------------------------------------------------------------------- #
# "" = use the Windows display language(s). Otherwise a tag like "en-US" or
# "de-DE"; the matching Windows OCR language pack must be installed.
DEFAULT_OCR_LANGUAGE = ""
# Small text is read much better when the image is enlarged first.
DEFAULT_OCR_UPSCALE_FACTOR = 2.0
OCR_UPSCALE_FACTOR_MIN = 1.0
OCR_UPSCALE_FACTOR_MAX = 4.0
# "OcrRegionCapture.exe --check-ocr" reads this test text and writes the result to the log.
OCR_CHECK_FLAG = "--check-ocr"
OCR_CHECK_TEXT = "OCR check 12345"
OCR_CHECK_IMAGE_SIZE = (480, 80)
OCR_CHECK_TEXT_POSITION = (10, 20)
OCR_CHECK_FONT_SIZE = 32

# --------------------------------------------------------------------------- #
# Layout reconstruction (turns OCR word boxes back into spaced text)
# --------------------------------------------------------------------------- #
DEFAULT_PRESERVE_LAYOUT = True
# Lines whose vertical centres are closer than this x line height share a row.
LAYOUT_ROW_MERGE_RATIO = 0.5
# Empty lines: the normal distance between rows ("line pitch") is measured
# from the capture; each extra pitch between two rows becomes one empty line.
# With too few rows to measure, pitch = line height x this ratio.
LAYOUT_FALLBACK_LINE_PITCH_RATIO = 1.3
LAYOUT_MIN_ROW_GAPS_FOR_PITCH_CALIBRATION = 2
LAYOUT_MAX_BLANK_LINES = 2
LAYOUT_MAX_SPACES_BETWEEN_WORDS = 40
LAYOUT_MAX_INDENT_SPACES = 80
# Space width guess (x average character width) when a capture has too few
# word gaps to measure the real space width.
LAYOUT_FALLBACK_SPACE_WIDTH_RATIO = 0.6
LAYOUT_MIN_GAPS_FOR_SPACE_CALIBRATION = 3

# --------------------------------------------------------------------------- #
# New-text detection / output (defaults, settings.json -> "text_capture")
# --------------------------------------------------------------------------- #
# 0..1. Two lines at least this similar are treated as "the same line" even if
# OCR misread a letter or two.
DEFAULT_TEXT_SIMILARITY_THRESHOLD = 0.8
DEFAULT_COPY_TEXT_TO_CLIPBOARD = True
# "" = off. Otherwise a file (relative to the exe folder or absolute) that
# every new piece of text is appended to - handy as a live-caption transcript.
DEFAULT_TRANSCRIPT_FILE = ""
# 0 = the hotkey captures once. >0 = the hotkey toggles automatic capturing
# every N milliseconds (live captioning).
DEFAULT_LIVE_CAPTION_INTERVAL_MS = 0
LIVE_CAPTION_MIN_INTERVAL_MS = 200
TRANSCRIPT_ENCODING = "utf-8"

# --------------------------------------------------------------------------- #
# Image capture (defaults, settings.json -> "image_capture")
# --------------------------------------------------------------------------- #
DEFAULT_IMAGE_FOLDER = "captures"
DEFAULT_IMAGE_FORMAT = "png"
SUPPORTED_IMAGE_FORMATS = ("png", "jpg", "bmp")
DEFAULT_COPY_IMAGE_TO_CLIPBOARD = True
# Used wherever transparency cannot be kept (clipboard, jpg, bmp).
DEFAULT_IMAGE_BACKGROUND = "#FFFFFF"
IMAGE_FILE_PREFIX_RECTANGLE = "image"
IMAGE_FILE_PREFIX_FREEFORM = "freeform"
IMAGE_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S_%f"
JPEG_QUALITY = 95

# --------------------------------------------------------------------------- #
# Silent point selection (defaults, settings.json -> "selection")
# --------------------------------------------------------------------------- #
# A started but unfinished selection is cancelled after this many seconds.
DEFAULT_SELECTION_TIMEOUT_SECONDS = 60.0
SELECTION_TIMEOUT_MIN_SECONDS = 1.0
# Freeform path: ignore mouse moves shorter than this (keeps the path small).
DEFAULT_FREEFORM_MIN_POINT_DISTANCE_PX = 3
MIN_FREEFORM_POINTS = 3
# Smallest width/height (pixels) accepted for any region or image.
MIN_CAPTURE_SIZE_PX = 3
# How long to wait for the mouse-hook thread to start / stop.
MOUSE_HOOK_THREAD_TIMEOUT_SECONDS = 2.0

# --------------------------------------------------------------------------- #
# Region overlay (shown only by set_region)
# --------------------------------------------------------------------------- #
# RGBA. Alpha must stay >= 1 or Windows lets clicks pass through the overlay.
OVERLAY_DIM_RGBA = (0, 0, 0, 90)
OVERLAY_SELECTION_RGBA = (255, 255, 255, 1)
OVERLAY_BORDER_RGBA = (255, 50, 50, 255)
OVERLAY_BORDER_WIDTH_PX = 2

# --------------------------------------------------------------------------- #
# Main window
# --------------------------------------------------------------------------- #
WINDOW_MIN_WIDTH_PX = 460
WINDOW_MIN_HEIGHT_PX = 520
OUTPUT_MAX_LINES = 5000
START_BUTTON_MIN_HEIGHT_PX = 40
STATUS_ERROR_COLOR = "#C62828"
STATUS_OK_COLOR = "#2E7D32"
