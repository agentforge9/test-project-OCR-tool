"""Main window: hotkey boxes, Start/Stop, status and the history of captured text.

The window only shows state and reports clicks (signals). It contains no
capture or settings logic; ``app.py`` decides what a click means.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import config
from ..config import HotkeyAction
from ..geometry import ScreenRect
from . import theme
from .hotkey_edit import HotkeyEdit

START_TEXT = "Start"
STOP_TEXT = "Stop"
SUBTITLE_TEXT = "New live-caption words into any text box, plus silent screenshots."
HINT_TEXT = "Click a box and press the keys together. Backspace clears. Locked while running."
NO_REGION_TEXT = "Region: not set yet (press Start, then the Set region hotkey)"
HISTORY_TITLE = "History (double-click an entry to copy it)"
_TEXT_ROLE = Qt.ItemDataRole.UserRole


class MainWindow(QWidget):
    start_stop_clicked = Signal()
    hotkey_edited = Signal(object, str)  # HotkeyAction, canonical text
    reset_hotkeys_clicked = Signal()
    open_folder_clicked = Signal()
    closing = Signal()

    def __init__(self, hotkeys: Mapping[str, str], icon: QIcon) -> None:
        super().__init__()
        self.setObjectName("MainWindow")
        self.setWindowTitle(config.APP_NAME)
        self.setWindowIcon(icon)
        self.setMinimumSize(config.WINDOW_MIN_WIDTH_PX, config.WINDOW_MIN_HEIGHT_PX)
        self.setStyleSheet(theme.STYLE_SHEET)

        self._edits: dict[HotkeyAction, HotkeyEdit] = {}
        self._reset_button = QPushButton("Reset to defaults")
        self._region_label = QLabel(NO_REGION_TEXT)
        self._start_button = QPushButton(START_TEXT)
        self._status_label = QLabel()
        self._history = QListWidget()

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_header(icon))
        layout.addWidget(self._build_hotkey_group(hotkeys))
        layout.addWidget(self._region_label)
        layout.addWidget(self._start_button)
        layout.addWidget(self._status_label)
        layout.addWidget(self._build_history_group(), stretch=1)

        self._region_label.setObjectName("Region")
        self._region_label.setWordWrap(True)
        self._start_button.setObjectName("StartButton")
        self._start_button.setMinimumHeight(config.START_BUTTON_MIN_HEIGHT_PX)
        self._start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_button.clicked.connect(self.start_stop_clicked)
        self._reset_button.clicked.connect(self.reset_hotkeys_clicked)
        self._status_label.setObjectName("Status")
        self._status_label.setWordWrap(True)
        self.set_running(False)

    def _build_header(self, icon: QIcon) -> QHBoxLayout:
        logo = QLabel()
        logo.setPixmap(icon.pixmap(theme.HEADER_ICON_SIZE_PX, theme.HEADER_ICON_SIZE_PX))
        title = QLabel(config.APP_NAME)
        title.setObjectName("Title")
        subtitle = QLabel(SUBTITLE_TEXT)
        subtitle.setObjectName("Subtitle")
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(title)
        texts.addWidget(subtitle)
        header = QHBoxLayout()
        header.addWidget(logo)
        header.addLayout(texts, stretch=1)
        return header

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
            label.setToolTip(f"{config.ACTION_TOOLTIPS[action]}\nsettings.json name: {action.value}")
            form.addRow(label, edit)
            self._edits[action] = edit
        hint = QLabel(HINT_TEXT)
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(hint, stretch=1)
        row.addWidget(self._reset_button)
        form.addRow(row)
        return group

    def _build_history_group(self) -> QGroupBox:
        group = QGroupBox(HISTORY_TITLE)
        self._history.setWordWrap(True)
        self._history.itemDoubleClicked.connect(self._copy_item)

        copy_button = QPushButton("Copy selected")
        copy_button.clicked.connect(lambda: self._copy_item(self._history.currentItem()))
        clear_button = QPushButton("Clear history")
        clear_button.clicked.connect(self._history.clear)
        folder_button = QPushButton("Open captures folder")
        folder_button.clicked.connect(self.open_folder_clicked)

        buttons = QHBoxLayout()
        buttons.addWidget(copy_button)
        buttons.addWidget(clear_button)
        buttons.addStretch(1)
        buttons.addWidget(folder_button)

        layout = QVBoxLayout(group)
        layout.addWidget(self._history)
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
        self._set_style_property(self._start_button, "running", running)
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
        self._set_style_property(self._status_label, "error", is_error)
        self._status_label.setText(message)

    def add_history(self, text: str) -> None:
        """Add one captured text, newest at the bottom (chronological order)."""
        stamp = datetime.now().strftime(config.HISTORY_TIME_FORMAT)
        item = QListWidgetItem(f"[{stamp}]  {text}")
        item.setData(_TEXT_ROLE, text)
        self._history.addItem(item)
        while self._history.count() > config.HISTORY_MAX_ITEMS:
            self._history.takeItem(0)
        self._history.scrollToBottom()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt API name)
        self.closing.emit()
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _copy_item(self, item: QListWidgetItem | None) -> None:
        if item is None:
            return
        QGuiApplication.clipboard().setText(item.data(_TEXT_ROLE))
        self.show_status("Copied to the clipboard.")

    @staticmethod
    def _set_style_property(widget: QWidget, name: str, value: bool) -> None:
        """Change a style-sheet property and make Qt re-apply the style."""
        widget.setProperty(name, "true" if value else "false")
        widget.style().unpolish(widget)
        widget.style().polish(widget)
