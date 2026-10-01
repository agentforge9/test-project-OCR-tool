"""Load and save ``settings.json`` (stored next to the exe).

Design notes:
* Settings objects are frozen dataclasses. Changing a value means creating a
  new object with ``dataclasses.replace``; worker threads can therefore read
  a settings snapshot without locks.
* Loading never crashes the app. A missing file gives defaults; a wrong or
  missing value falls back to its default and a warning is reported; a file
  that is not valid JSON is backed up and replaced with defaults.
* Saving is atomic (write a temp file, then rename) so a crash can never
  leave a half-written settings file behind.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from . import config
from .config import HotkeyAction
from .geometry import ScreenRect
from .hotkey_spec import HotkeyError, parse_optional

log = logging.getLogger(__name__)

JSON_INDENT = 2
BROKEN_FILE_SUFFIX_FORMAT = ".broken-%Y%m%d-%H%M%S"


# --------------------------------------------------------------------------- #
# Settings model. Every default comes from config.py.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class OcrSettings:
    language: str = config.DEFAULT_OCR_LANGUAGE
    upscale_factor: float = config.DEFAULT_OCR_UPSCALE_FACTOR

    def __post_init__(self) -> None:
        if not config.OCR_UPSCALE_FACTOR_MIN <= self.upscale_factor <= config.OCR_UPSCALE_FACTOR_MAX:
            raise ValueError(
                f"upscale_factor must be between {config.OCR_UPSCALE_FACTOR_MIN} "
                f"and {config.OCR_UPSCALE_FACTOR_MAX}"
            )


@dataclass(frozen=True)
class TextCaptureSettings:
    preserve_layout: bool = config.DEFAULT_PRESERVE_LAYOUT
    similarity_threshold: float = config.DEFAULT_TEXT_SIMILARITY_THRESHOLD
    copy_to_clipboard: bool = config.DEFAULT_COPY_TEXT_TO_CLIPBOARD
    transcript_file: str = config.DEFAULT_TRANSCRIPT_FILE
    live_caption_interval_ms: int = config.DEFAULT_LIVE_CAPTION_INTERVAL_MS

    def __post_init__(self) -> None:
        if not 0.0 < self.similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be greater than 0 and at most 1")
        if self.live_caption_interval_ms != 0 and self.live_caption_interval_ms < config.LIVE_CAPTION_MIN_INTERVAL_MS:
            raise ValueError(f"live_caption_interval_ms must be 0 or at least {config.LIVE_CAPTION_MIN_INTERVAL_MS}")


@dataclass(frozen=True)
class ImageCaptureSettings:
    output_folder: str = config.DEFAULT_IMAGE_FOLDER
    file_format: str = config.DEFAULT_IMAGE_FORMAT
    copy_to_clipboard: bool = config.DEFAULT_COPY_IMAGE_TO_CLIPBOARD
    background_color: str = config.DEFAULT_IMAGE_BACKGROUND

    def __post_init__(self) -> None:
        if self.file_format.lower() not in config.SUPPORTED_IMAGE_FORMATS:
            raise ValueError(f"file_format must be one of {', '.join(config.SUPPORTED_IMAGE_FORMATS)}")
        if not self.output_folder.strip():
            raise ValueError("output_folder must not be empty")


@dataclass(frozen=True)
class SelectionSettings:
    timeout_seconds: float = config.DEFAULT_SELECTION_TIMEOUT_SECONDS
    freeform_min_point_distance_px: int = config.DEFAULT_FREEFORM_MIN_POINT_DISTANCE_PX

    def __post_init__(self) -> None:
        if self.timeout_seconds < config.SELECTION_TIMEOUT_MIN_SECONDS:
            raise ValueError(f"timeout_seconds must be at least {config.SELECTION_TIMEOUT_MIN_SECONDS}")
        if self.freeform_min_point_distance_px < 0:
            raise ValueError("freeform_min_point_distance_px must not be negative")


def default_hotkeys() -> dict[str, str]:
    return {action.value: text for action, text in config.DEFAULT_HOTKEYS.items()}


@dataclass(frozen=True)
class AppSettings:
    # "hotkeys" is first on purpose: it then sits at the top of settings.json.
    hotkeys: Mapping[str, str] = field(default_factory=default_hotkeys)
    region: ScreenRect | None = None
    ocr: OcrSettings = field(default_factory=OcrSettings)
    text_capture: TextCaptureSettings = field(default_factory=TextCaptureSettings)
    image_capture: ImageCaptureSettings = field(default_factory=ImageCaptureSettings)
    selection: SelectionSettings = field(default_factory=SelectionSettings)

    def with_hotkey(self, action: HotkeyAction, text: str) -> AppSettings:
        return replace(self, hotkeys={**self.hotkeys, action.value: text})

    def to_dict(self) -> dict[str, Any]:
        return {
            "hotkeys": {action.value: self.hotkeys.get(action.value, "") for action in HotkeyAction},
            "region": self.region.to_dict() if self.region else None,
            "ocr": _section_to_dict(self.ocr),
            "text_capture": _section_to_dict(self.text_capture),
            "image_capture": _section_to_dict(self.image_capture),
            "selection": _section_to_dict(self.selection),
        }


# --------------------------------------------------------------------------- #
# Tolerant parsing: bad values fall back to defaults with a warning.
# --------------------------------------------------------------------------- #
_Section = TypeVar("_Section")


def _section_to_dict(section: object) -> dict[str, Any]:
    return {f.name: getattr(section, f.name) for f in fields(section)}  # type: ignore[arg-type]


def _matches_type(value: Any, default: Any) -> bool:
    """bool is a subclass of int in Python, so it needs special care."""
    if isinstance(default, bool) or isinstance(value, bool):
        return isinstance(value, bool) and isinstance(default, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float))
    return isinstance(value, type(default))


def _parse_section(cls: type[_Section], raw: Any, name: str, warnings: list[str]) -> _Section:
    defaults = cls()
    if raw is None:
        return defaults
    if not isinstance(raw, Mapping):
        warnings.append(f"'{name}' must be an object; using defaults.")
        return defaults

    values: dict[str, Any] = {}
    known = {f.name for f in fields(cls)}  # type: ignore[arg-type]
    for key in raw.keys() - known:
        warnings.append(f"Unknown setting '{name}.{key}' was ignored.")
    for key in known & raw.keys():
        default = getattr(defaults, key)
        value = raw[key]
        if not _matches_type(value, default):
            warnings.append(f"'{name}.{key}' has the wrong type; using default {default!r}.")
            continue
        values[key] = float(value) if isinstance(default, float) else value

    try:
        return replace(defaults, **values)
    except ValueError as exc:
        warnings.append(f"'{name}': {exc}; using defaults for this section.")
        return defaults


def _parse_hotkeys(raw: Any, warnings: list[str]) -> dict[str, str]:
    hotkeys = default_hotkeys()
    if raw is None:
        return hotkeys
    if not isinstance(raw, Mapping):
        warnings.append("'hotkeys' must be an object; using default hotkeys.")
        return hotkeys

    valid_actions = {action.value for action in HotkeyAction}
    for key in raw.keys() - valid_actions:
        warnings.append(f"Unknown hotkey action '{key}' was ignored.")
    for action in valid_actions & raw.keys():
        text = raw[action]
        if not isinstance(text, str):
            warnings.append(f"Hotkey '{action}' must be text; using default.")
            continue
        try:
            spec = parse_optional(text)
        except HotkeyError as exc:
            warnings.append(f"Hotkey '{action}': {exc} Using default '{hotkeys[action]}'.")
            continue
        hotkeys[action] = str(spec) if spec else ""
    return hotkeys


def _parse_region(raw: Any, warnings: list[str]) -> ScreenRect | None:
    if raw is None:
        return None
    try:
        return ScreenRect.from_dict(raw)
    except ValueError as exc:
        warnings.append(f"'region' is invalid ({exc}); set the region again.")
        return None


def settings_from_dict(data: Any) -> tuple[AppSettings, list[str]]:
    """Build settings from parsed JSON. Returns (settings, warnings)."""
    warnings: list[str] = []
    if not isinstance(data, Mapping):
        return AppSettings(), ["Settings file must contain a JSON object; using defaults."]
    known_sections = {f.name for f in fields(AppSettings)}
    for key in data.keys() - known_sections:
        warnings.append(f"Unknown setting '{key}' was ignored.")
    settings = AppSettings(
        hotkeys=_parse_hotkeys(data.get("hotkeys"), warnings),
        region=_parse_region(data.get("region"), warnings),
        ocr=_parse_section(OcrSettings, data.get("ocr"), "ocr", warnings),
        text_capture=_parse_section(TextCaptureSettings, data.get("text_capture"), "text_capture", warnings),
        image_capture=_parse_section(ImageCaptureSettings, data.get("image_capture"), "image_capture", warnings),
        selection=_parse_section(SelectionSettings, data.get("selection"), "selection", warnings),
    )
    return settings, warnings


# --------------------------------------------------------------------------- #
# File storage
# --------------------------------------------------------------------------- #
class SettingsStore:
    """Reads and writes one settings file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> tuple[AppSettings, list[str]]:
        """Return (settings, warnings). Never raises for bad file content."""
        if not self.exists():
            return AppSettings(), []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            backup = self._backup_broken_file()
            return AppSettings(), [
                f"{self.path.name} is not valid JSON ({exc.msg}, line {exc.lineno}). "
                f"It was saved as {backup.name} and defaults are used."
            ]
        except OSError as exc:
            return AppSettings(), [f"Could not read {self.path.name}: {exc}. Using defaults."]
        return settings_from_dict(data)

    def save(self, settings: AppSettings) -> None:
        """Atomically write settings. Raises OSError if the folder is not writable."""
        text = json.dumps(settings.to_dict(), indent=JSON_INDENT, ensure_ascii=False) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            os.replace(temp_name, self.path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
        log.debug("Settings saved to %s", self.path)

    def _backup_broken_file(self) -> Path:
        backup = self.path.with_name(self.path.name + datetime.now().strftime(BROKEN_FILE_SUFFIX_FORMAT))
        try:
            os.replace(self.path, backup)
        except OSError:
            log.exception("Could not back up broken settings file")
        return backup
