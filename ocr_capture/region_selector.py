"""Drag-to-select overlay used by the set_region hotkey.

One semi-transparent window covers each monitor. Press the left button,
drag, release: the rectangle becomes the OCR region. Esc or right click
cancels.

Screen positions are read with Win32 ``GetCursorPos`` (physical pixels)
instead of converting Qt's DPI-scaled coordinates, so the region is exact
on every monitor, whatever its scaling.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QScreen,
)
from PySide6.QtWidgets import QWidget

from . import config
from .geometry import Point, ScreenRect
from .win32.api import get_cursor_pos


class _Overlay(QWidget):
    def __init__(self, screen: QScreen, owner: RegionSelector) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self._owner = owner
        self._drag_start: QPointF | None = None
        self._drag_now: QPointF | None = None
        self._start_physical: Point | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 (Qt API name)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(*config.OVERLAY_DIM_RGBA))
        if self._drag_start is not None and self._drag_now is not None:
            selection = QRectF(self._drag_start, self._drag_now).normalized()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(selection, QColor(*config.OVERLAY_SELECTION_RGBA))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(*config.OVERLAY_BORDER_RGBA), config.OVERLAY_BORDER_WIDTH_PX))
            painter.drawRect(selection)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton:
            self._owner.cancel()
        elif event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = self._drag_now = event.position()
            self._start_physical = get_cursor_pos()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_start is not None:
            self._drag_now = event.position()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._start_physical is not None:
            self._owner.finish(ScreenRect.from_corners(self._start_physical, get_cursor_pos()))

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._owner.cancel()


class RegionSelector(QObject):
    selected = Signal(object)  # ScreenRect
    cancelled = Signal(str)  # user-facing reason

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._overlays: list[_Overlay] = []

    @property
    def is_active(self) -> bool:
        return bool(self._overlays)

    def start(self) -> None:
        self._close_overlays()
        self._overlays = [_Overlay(screen, self) for screen in QGuiApplication.screens()]
        for overlay in self._overlays:
            overlay.show()
        # Keyboard focus for Esc. Windows may refuse focus when another app is
        # in front; right click always works as a fallback.
        under_cursor = QGuiApplication.screenAt(QCursor.pos())
        target = next((o for o in self._overlays if o.screen() == under_cursor), self._overlays[0])
        target.raise_()
        target.activateWindow()

    def finish(self, rect: ScreenRect) -> None:
        self._close_overlays()
        if rect.is_at_least(config.MIN_CAPTURE_SIZE_PX):
            self.selected.emit(rect)
        else:
            self.cancelled.emit(f"Region too small (minimum {config.MIN_CAPTURE_SIZE_PX} px). Drag a bigger area.")

    def cancel(self) -> None:
        if self.is_active:
            self._close_overlays()
            self.cancelled.emit("Region selection cancelled.")

    def _close_overlays(self) -> None:
        overlays, self._overlays = self._overlays, []
        for overlay in overlays:
            overlay.close()
