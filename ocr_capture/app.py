"""App start-up and wiring: window <-> settings <-> hotkeys <-> capture actions."""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from types import TracebackType

from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__, config, paths
from .capture_controller import CaptureController
from .config import HotkeyAction
from .geometry import ScreenRect
from .hotkey_spec import HotkeyError, parse_bindings
from .settings import AppSettings, SettingsStore, default_hotkeys
from .ui.main_window import MainWindow
from .win32.hotkeys import GlobalHotkeyManager, HotkeyRegistrationError

log = logging.getLogger(__name__)


class Application(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._store = SettingsStore(paths.settings_path())
        self._settings, warnings = self._store.load()

        self._window = MainWindow(self._settings.hotkeys, _load_icon())
        self._window.set_region(self._settings.region)
        # winId() creates the native window; hotkey messages are sent to it.
        self._hotkeys = GlobalHotkeyManager(int(self._window.winId()), self)
        self._controller = CaptureController(lambda: self._settings, parent=self)
        self._connect_signals()

        # Creates settings.json on first start, and rewrites older files in
        # the current format (new options appear, removed ones disappear).
        self._save()
        if warnings:
            self._report_warnings(warnings)

    def show(self) -> None:
        self._window.show()

    def _connect_signals(self) -> None:
        w, c = self._window, self._controller
        w.start_stop_clicked.connect(self._toggle_running)
        w.hotkey_edited.connect(self._on_hotkey_edited)
        w.reset_hotkeys_clicked.connect(self._on_reset_hotkeys)
        w.open_folder_clicked.connect(self._on_open_folder)
        w.closing.connect(self._on_closing)
        self._hotkeys.activated.connect(c.handle_action)
        c.status.connect(w.show_status)
        c.text_delivered.connect(w.add_history)
        c.image_pasted.connect(lambda path: w.add_history(f"[Image] {path}"))
        c.region_selected.connect(self._on_region_selected)

    # ------------------------------------------------------------------ #
    # Start / Stop
    # ------------------------------------------------------------------ #
    def _toggle_running(self) -> None:
        if self._hotkeys.is_active:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        # Pick up edits made to settings.json while the app was open, so
        # changing a hotkey line there only needs Stop -> Start.
        self._reload_settings_from_disk()
        try:
            bindings = parse_bindings(self._settings.hotkeys)
            if not bindings:
                raise HotkeyError("All hotkeys are empty. Set at least one hotkey.")
            self._hotkeys.register_all(bindings)
        except (HotkeyError, HotkeyRegistrationError) as exc:
            self._window.show_status(str(exc), is_error=True)
            return
        self._window.set_running(True)
        self._controller.activate()
        log.info("Started with hotkeys %s", {a: str(s) for a, s in bindings.items()})

    def _stop(self) -> None:
        self._controller.stop_all()
        self._hotkeys.unregister_all()
        self._window.set_running(False)
        log.info("Stopped")

    def _reload_settings_from_disk(self) -> None:
        if not self._store.exists():
            self._save()
            return
        fresh, warnings = self._store.load()
        if warnings:
            self._report_warnings(warnings)
        if fresh != self._settings:
            log.info("settings.json changed on disk; reloaded")
            self._settings = fresh
            self._window.set_hotkeys(fresh.hotkeys)
            self._window.set_region(fresh.region)

    # ------------------------------------------------------------------ #
    # Settings edits from the window
    # ------------------------------------------------------------------ #
    def _on_hotkey_edited(self, action: HotkeyAction, text: str) -> None:
        candidate = self._settings.with_hotkey(action, text)
        try:
            parse_bindings(candidate.hotkeys)
        except HotkeyError as exc:
            self._window.set_hotkey(action, self._settings.hotkeys.get(action.value, ""))
            self._window.show_status(str(exc), is_error=True)
            return
        self._settings = candidate
        if self._save():
            self._window.show_status(f"Saved {action.value} = {text or '(none)'}")

    def _on_reset_hotkeys(self) -> None:
        self._settings = replace(self._settings, hotkeys=default_hotkeys())
        self._window.set_hotkeys(self._settings.hotkeys)
        if self._save():
            self._window.show_status("Hotkeys reset to defaults.")

    def _on_region_selected(self, rect: ScreenRect) -> None:
        self._settings = replace(self._settings, region=rect)
        self._window.set_region(rect)
        self._save()

    def _save(self) -> bool:
        try:
            self._store.save(self._settings)
        except OSError as exc:
            log.exception("Saving settings failed")
            self._window.show_status(
                f"Could not save {self._store.path}: {exc}. Move the app to a folder you can write to.",
                is_error=True,
            )
            return False
        return True

    def _report_warnings(self, warnings: list[str]) -> None:
        for warning in warnings:
            log.warning("Settings: %s", warning)
        self._window.show_status("Settings problems (defaults used):\n" + "\n".join(warnings), is_error=True)

    def _on_open_folder(self) -> None:
        folder = paths.resolve_user_path(self._settings.image_capture.output_folder)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._window.show_status(f"Could not create {folder}: {exc}", is_error=True)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _on_closing(self) -> None:
        self._controller.shutdown()
        self._hotkeys.close()


# ---------------------------------------------------------------------- #
# Process-level setup
# ---------------------------------------------------------------------- #
def _load_icon() -> QIcon:
    path = paths.resource_path(config.APP_ICON_FILE)
    if not path.is_file():
        log.warning("App icon not found: %s", path)
    return QIcon(str(path))


def _set_taskbar_identity() -> None:
    """Without this, Windows groups the app under python.exe and shows its icon."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(config.APP_USER_MODEL_ID)
    except OSError:
        log.warning("Could not set the taskbar app id", exc_info=True)


def _configure_logging() -> None:
    handlers: list[logging.Handler]
    try:
        handlers = [
            RotatingFileHandler(
                paths.log_path(),
                maxBytes=config.LOG_MAX_BYTES,
                backupCount=config.LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
        ]
    except OSError:
        handlers = [logging.StreamHandler()]
    logging.basicConfig(level=logging.INFO, format=config.LOG_FORMAT, handlers=handlers, force=True)


def _install_crash_handlers() -> None:
    """Log unexpected errors and tell the user instead of dying silently."""

    def on_exception(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        log.critical("Unhandled error", exc_info=(exc_type, exc, tb))
        if QApplication.instance() is not None and threading.current_thread() is threading.main_thread():
            QMessageBox.critical(None, config.APP_NAME, f"Unexpected error: {exc}\n\nDetails: {paths.log_path()}")

    sys.excepthook = on_exception
    threading.excepthook = lambda args: log.critical(
        "Unhandled error in thread %s", args.thread, exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )


def _check_ocr() -> int:
    """``--check-ocr``: read a generated test image and log the result (no window)."""
    from PIL import Image, ImageDraw, ImageFont

    from .ocr_engine import WindowsOcrRecognizer
    from .text_layout import build_text

    image = Image.new("RGB", config.OCR_CHECK_IMAGE_SIZE, "white")
    font = ImageFont.load_default(size=config.OCR_CHECK_FONT_SIZE)
    ImageDraw.Draw(image).text(config.OCR_CHECK_TEXT_POSITION, config.OCR_CHECK_TEXT, fill="black", font=font)
    settings, _ = SettingsStore(paths.settings_path()).load()
    try:
        lines = WindowsOcrRecognizer(settings.ocr.language, settings.ocr.upscale_factor).recognize(image)
    except Exception:
        log.exception("OCR check failed")
        return 1
    text = build_text(lines)
    log.info("OCR check read %r (expected %r)", text, config.OCR_CHECK_TEXT)
    return 0 if text.strip() else 1


def main() -> int:
    _configure_logging()
    log.info("%s %s starting from %s", config.APP_NAME, __version__, paths.app_dir())
    if config.OCR_CHECK_FLAG in sys.argv[1:]:
        return _check_ocr()
    _set_taskbar_identity()
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(config.APP_NAME)
    qt_app.setWindowIcon(_load_icon())
    _install_crash_handlers()
    app = Application()
    app.show()
    return qt_app.exec()
