"""Paste the clipboard into whatever text box has the keyboard focus.

The hotkey is still held when the text is ready (e.g. Alt of Alt+.). If we
pressed Ctrl+V now, the target app would see Ctrl+Alt+V. So we wait (polling,
without blocking the UI) until all modifier keys are released, then send
Ctrl+V. Releasing a key the user is holding ourselves is not an option: a
lone Alt release opens the menu bar in many programs.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal

from . import config
from .win32 import keyboard

_MS_PER_SECOND = 1000


class AutoPaster(QObject):
    failed = Signal(str)  # user-facing reason

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._deadline = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(config.PASTE_KEY_RELEASE_POLL_MS)
        self._timer.timeout.connect(self._try_paste)

    def paste_clipboard(self) -> None:
        """Send Ctrl+V as soon as the user's modifier keys are released."""
        self._deadline = time.monotonic() + config.PASTE_KEY_RELEASE_TIMEOUT_MS / _MS_PER_SECOND
        self._timer.start()
        self._try_paste()

    def cancel(self) -> None:
        self._timer.stop()

    def _try_paste(self) -> None:
        if keyboard.modifiers_held():
            if time.monotonic() > self._deadline:
                self._timer.stop()
                self.failed.emit("Not pasted: keys were held down too long. The text is on the clipboard.")
            return
        self._timer.stop()
        if keyboard.foreground_is_own_window():
            self.failed.emit("Not pasted into this window. Click into the target text box first.")
            return
        try:
            keyboard.send_ctrl_v()
        except OSError as exc:
            self.failed.emit(f"{exc}. The text is on the clipboard.")
