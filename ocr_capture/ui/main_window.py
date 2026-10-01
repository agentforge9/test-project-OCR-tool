"""Main window: hotkey boxes, Start/Stop, status and captured text.

The window only shows state and reports clicks (signals). It contains no
capture or settings logic; ``app.py`` decides what a click means.
"""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import config
from ..config import HotkeyAction
from ..geometry import ScreenRect
from .hotkey_edit import HotkeyEdit

START_TEXT = "Start"
STOP_TEXT = "Stop"
HINT_TEXT = "Click a box and press the keys together. Backspace clears a box. Boxes are locked while running."
NO_REGION_TEXT = "Region: not set (press the set_region hotkey after Start)"
OUTPUT_SEPARATOR = "-" * 40


class MainWindow(QWidget):
    start_stop_clicked = Signal()
    hotkey_edited = Signal(object, str)  # HotkeyAction, canonical text
    reset_hotkeys_clicked = Signal()
    clear_output_clicked = Signal()
    open_folder_clicked = Signal()
    closing = Signal()

    def __init__(self, hotkeys: Mapping[str, str]) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.setMinimumSize(config.WINDOW_MIN_WIDTH_PX, config.WINDOW_MIN_HEIGHT_PX)

        self._edits: dict[HotkeyAction, HotkeyEdit] = {}
        self._reset_button = QPushButton("Reset hotkeys to defaults")
        self._region_label = QLabel(NO_REGION_TEXT)
        self._start_button = QPushButton(START_TEXT)
        self._status_label = QLabel()
        self._output = QPlainTextEdit()

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_hotkey_group(hotkeys))
        layout.addWidget(self._region_label)
        layout.addWidget(self._start_button)
        layout.addWidget(self._status_label)
        layout.addWidget(self._build_output_group(), stretch=1)

        self._start_button.setMinimumHeight(config.START_BUTTON_MIN_HEIGHT_PX)
        self._start_button.clicked.connect(self.start_stop_clicked)
        self._reset_button.clicked.connect(self.reset_hotkeys_clicked)
        self._status_label.setWordWrap(True)
        self._region_label.setWordWrap(True)
        self.set_running(False)

    def _build_hotkey_group(self, hotkeys: Mapping[str, str]) -> QGroupBox:
        group = QGroupBox("Hotkeys")
        form = QFormLayout(group)
        for action in HotkeyAction:
            edit = HotkeyEdit()
            edit.set_hotkey(hotkeys.get(action.value, ""))
            edit.setToolTip(config.ACTION_TOOLTIPS[action])
            edit.hotkey_entered.connect(lambda text, a=action: self.hotkey_edited.emit(a, text))
            edit.rejected.connect(lambda reason: self.show_status(reason, is_error=True))
            label = QLabel(config.ACTION_LABELS[action])
            label.setToolTip(config.ACTION_TOOLTIPS[action])
            form.addRow(label, edit)
            self._edits[action] = edit
        hint = QLabel(HINT_TEXT)
        hint.setWordWrap(True)
        form.addRow(hint)
        form.addRow(self._reset_button)
        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("New text (also copied to the clipboard)")
        self._output.setReadOnly(True)
        self._output.setMaximumBlockCount(config.OUTPUT_MAX_LINES)
        self._output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        clear_button = QPushButton("Clear")
        clear_button.setToolTip("Clear this box and forget the last capture (next capture returns all text).")
        clear_button.clicked.connect(self.clear_output_clicked)
        folder_button = QPushButton("Open captures folder")
        folder_button.clicked.connect(self.open_folder_clicked)

        buttons = QHBoxLayout()
        buttons.addWidget(clear_button)
        buttons.addStretch(1)
        buttons.addWidget(folder_button)

        layout = QVBoxLayout(group)
        layout.addWidget(self._output)
        layout.addLayout(buttons)
        return group

    # ------------------------------------------------------------------ #
    # State updates called by app.py
    # ------------------------------------------------------------------ #
    def set_hotkeys(self, hotkeys: Mapping[str, str]) -> None:
        for action, edit in self._edits.items():
            edit.set_hotkey(hotkeys.get(action.value, ""))

    def set_hotkey(self, action: HotkeyAction, text: str) -> None:
        self._edits[action].set_hotkey(text)

    def set_running(self, running: bool) -> None:
        self._start_button.setText(STOP_TEXT if running else START_TEXT)
        for edit in self._edits.values():
            edit.setEnabled(not running)
        self._reset_button.setEnabled(not running)
        self.show_status(
            "Running: hotkeys work everywhere on this PC." if running else "Stopped: hotkeys are off.",
            is_error=False,
        )

    def set_region(self, rect: ScreenRect | None) -> None:
        self._region_label.setText(f"Region: {rect}" if rect else NO_REGION_TEXT)

    def show_status(self, message: str, is_error: bool = False) -> None:
        color = config.STATUS_ERROR_COLOR if is_error else config.STATUS_OK_COLOR
        self._status_label.setStyleSheet(f"color: {color};")
        self._status_label.setText(message)

    def append_output(self, text: str) -> None:
        if self._output.blockCount() > 1 or self._output.toPlainText():
            self._output.appendPlainText(OUTPUT_SEPARATOR)
        self._output.appendPlainText(text)

    def clear_output(self) -> None:
        self._output.clear()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt API name)
        self.closing.emit()
        super().closeEvent(event)
