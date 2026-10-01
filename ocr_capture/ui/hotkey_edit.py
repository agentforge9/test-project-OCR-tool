"""Text box that records a hotkey by pressing it.

Click the box, then press the keys together (e.g. hold Alt+Shift, press /).
The box fills in the canonical text ("Alt+Shift+Slash") by itself.
* While only modifiers are held it previews them ("Alt+Shift+...").
* Backspace or Delete (alone) clears the hotkey (= action disabled).
* Esc (alone) cancels the edit and keeps the old hotkey.

Keys are read by their Windows virtual-key code, so the result is exactly
what ``RegisterHotKey`` needs, whatever the keyboard layout.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFocusEvent, QGuiApplication, QKeyEvent
from PySide6.QtWidgets import QLineEdit, QWidget

from ..hotkey_spec import (
    MODIFIER_KEY_CODES,
    HotkeyError,
    HotkeySpec,
    Modifier,
    format_modifiers,
    key_name_for_code,
)

_QT_TO_MODIFIER = {
    Qt.KeyboardModifier.ControlModifier: Modifier.CTRL,
    Qt.KeyboardModifier.AltModifier: Modifier.ALT,
    Qt.KeyboardModifier.ShiftModifier: Modifier.SHIFT,
    Qt.KeyboardModifier.MetaModifier: Modifier.WIN,
}
_QT_MODIFIER_KEYS = frozenset({Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta, Qt.Key.Key_AltGr})
_CLEAR_KEYS = frozenset({Qt.Key.Key_Backspace, Qt.Key.Key_Delete})
_FOCUS_KEYS = frozenset({Qt.Key.Key_Tab, Qt.Key.Key_Backtab})
PREVIEW_SUFFIX = "..."
PLACEHOLDER = "(none) - click and press keys"


def _to_modifiers(qt_modifiers: Qt.KeyboardModifier) -> Modifier:
    result = Modifier.NONE
    for qt_flag, modifier in _QT_TO_MODIFIER.items():
        if qt_modifiers & qt_flag:
            result |= modifier
    return result


class HotkeyEdit(QLineEdit):
    hotkey_entered = Signal(str)  # canonical text, "" = cleared
    rejected = Signal(str)  # user-facing reason

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._committed = ""
        self.setPlaceholderText(PLACEHOLDER)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, False)

    def hotkey(self) -> str:
        return self._committed

    def set_hotkey(self, text: str) -> None:
        self._committed = text
        self.setText(text)

    def event(self, event: QEvent) -> bool:
        # Tab would otherwise move focus before keyPressEvent sees it.
        if event.type() == QEvent.Type.KeyPress and event.key() in _FOCUS_KEYS:
            self.keyPressEvent(event)
            return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt API name)
        if event.isAutoRepeat():
            return
        modifiers = _to_modifiers(event.modifiers())
        key = event.key()

        if key in _QT_MODIFIER_KEYS or event.nativeVirtualKey() in MODIFIER_KEY_CODES:
            self.setText(format_modifiers(modifiers) + PREVIEW_SUFFIX)
            return
        if modifiers == Modifier.NONE and key == Qt.Key.Key_Escape:
            self._show_committed()
            self.clearFocus()
            return
        if modifiers == Modifier.NONE and key in _CLEAR_KEYS:
            self._commit("")
            return

        key_name = key_name_for_code(event.nativeVirtualKey())
        if key_name is None:
            self._reject("This key cannot be used as a hotkey.")
            return
        try:
            spec = HotkeySpec(modifiers, key_name)
        except HotkeyError as exc:
            self._reject(str(exc))
            return
        self._commit(str(spec))

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        # All keys released without a main key: drop the "Alt+..." preview.
        if _to_modifiers(QGuiApplication.queryKeyboardModifiers()) == Modifier.NONE:
            self._show_committed()

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        self._show_committed()
        super().focusOutEvent(event)

    def _commit(self, text: str) -> None:
        self.set_hotkey(text)
        self.hotkey_entered.emit(text)

    def _reject(self, reason: str) -> None:
        self._show_committed()
        self.rejected.emit(reason)

    def _show_committed(self) -> None:
        self.setText(self._committed)
