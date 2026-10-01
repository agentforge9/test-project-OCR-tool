"""System-wide hotkeys via Win32 ``RegisterHotKey``.

``RegisterHotKey`` makes Windows send ``WM_HOTKEY`` to our window whenever
the key combination is pressed, no matter which program has focus. A Qt
native event filter catches that message and emits ``activated``.

Registration is all-or-nothing: if one hotkey is already taken by another
program, none stay registered, so the app is never half-working.
"""

from __future__ import annotations

import ctypes
import logging
from collections.abc import Mapping
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, QTimer, Signal

from .. import config
from ..hotkey_spec import HotkeySpec
from . import api

log = logging.getLogger(__name__)

_QT_WINDOW_MESSAGE = b"windows_generic_MSG"


class HotkeyRegistrationError(RuntimeError):
    """One or more hotkeys could not be registered. The message is user-facing."""


class _WmHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, hwnd: int, on_hotkey) -> None:
        super().__init__()
        self._hwnd = hwnd
        self._on_hotkey = on_hotkey

    def nativeEventFilter(self, event_type, message):  # noqa: N802 (Qt API name)
        if bytes(event_type) == _QT_WINDOW_MESSAGE:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == api.WM_HOTKEY and msg.hWnd == self._hwnd:
                self._on_hotkey(int(msg.wParam))
                return True, 0
        return False, 0


class GlobalHotkeyManager(QObject):
    """Registers hotkeys for a window and emits ``activated(action_id)``."""

    activated = Signal(str)

    def __init__(self, hwnd: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._hwnd = hwnd
        self._actions_by_id: dict[int, str] = {}
        self._filter = _WmHotkeyFilter(hwnd, self._on_hotkey_id)
        QCoreApplication.instance().installNativeEventFilter(self._filter)

    @property
    def is_active(self) -> bool:
        return bool(self._actions_by_id)

    def register_all(self, bindings: Mapping[str, HotkeySpec]) -> None:
        """Register every binding (action id -> hotkey). Raises HotkeyRegistrationError."""
        self.unregister_all()
        flags_extra = api.MOD_NOREPEAT if config.HOTKEY_SUPPRESS_AUTOREPEAT else 0
        failures: list[str] = []
        for index, (action, spec) in enumerate(bindings.items()):
            hotkey_id = config.HOTKEY_ID_BASE + index
            if api.user32.RegisterHotKey(self._hwnd, hotkey_id, int(spec.modifiers) | flags_extra, spec.virtual_key):
                self._actions_by_id[hotkey_id] = action
                log.info("Registered hotkey %s for %s", spec, action)
            else:
                failures.append(f"{spec} ({action}): {self._describe_failure()}")

        if failures:
            self.unregister_all()
            raise HotkeyRegistrationError("These hotkeys could not be started:\n" + "\n".join(failures))

    def unregister_all(self) -> None:
        for hotkey_id in self._actions_by_id:
            if not api.user32.UnregisterHotKey(self._hwnd, hotkey_id):
                log.warning("UnregisterHotKey(%s) failed: %s", hotkey_id, api.last_error_message())
        self._actions_by_id.clear()

    def close(self) -> None:
        self.unregister_all()
        QCoreApplication.instance().removeNativeEventFilter(self._filter)

    def _on_hotkey_id(self, hotkey_id: int) -> None:
        action = self._actions_by_id.get(hotkey_id)
        if action is not None:
            # Defer: never run app logic inside the native event filter itself.
            QTimer.singleShot(0, lambda: self.activated.emit(action))

    @staticmethod
    def _describe_failure() -> str:
        if ctypes.get_last_error() == api.ERROR_HOTKEY_ALREADY_REGISTERED:
            return "already used by another program or by Windows"
        return api.last_error_message()
