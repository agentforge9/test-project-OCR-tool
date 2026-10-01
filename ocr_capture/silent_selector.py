"""One silent point-picking session: mouse hook + state machine + timeout.

Nothing is shown on screen and the cursor is untouched. The session ends
when the user finishes (``completed``), right-clicks, times out, or the app
cancels it (``cancelled``). Both signals are delivered on the UI thread.
"""

from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QTimer, Signal

from .geometry import Point
from .point_picker import MouseEvent, PickerPhase, PickMode, PointPicker
from .win32.mouse_hook import LowLevelMouseHook

log = logging.getLogger(__name__)

_MS_PER_SECOND = 1000


class SilentSelector(QObject):
    completed = Signal(object, list)  # PickMode, list[Point]
    cancelled = Signal(str)  # user-facing reason
    # Internal: emitted from the hook thread, received on the UI thread.
    _picker_finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._picker: PointPicker | None = None
        self._hook = LowLevelMouseHook(self._on_mouse_event)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(lambda: self.cancel("Selection timed out."))
        self._picker_finished.connect(self._on_picker_finished)

    @property
    def active_mode(self) -> PickMode | None:
        with self._lock:
            return self._picker.mode if self._picker else None

    def start(self, mode: PickMode, timeout_seconds: float, min_point_distance: float) -> None:
        """Begin listening. Raises MouseHookError if the mouse cannot be hooked."""
        self.cancel("Replaced by a new selection.")
        with self._lock:
            self._picker = PointPicker(mode, min_point_distance)
        try:
            self._hook.start()
        except Exception:
            with self._lock:
                self._picker = None
            raise
        self._timeout.start(round(timeout_seconds * _MS_PER_SECOND))
        log.info("Silent %s selection started", mode.value)

    def cancel(self, reason: str) -> None:
        if self._end_session() is not None:
            log.info("Selection cancelled: %s", reason)
            self.cancelled.emit(reason)

    def _end_session(self) -> PointPicker | None:
        self._timeout.stop()
        self._hook.stop()
        with self._lock:
            picker, self._picker = self._picker, None
        return picker

    def _on_mouse_event(self, event: MouseEvent) -> bool:
        """Runs on the hook thread: must stay fast."""
        with self._lock:
            picker = self._picker
            if picker is None:
                return False
            swallow = picker.feed(event)
            finished = picker.is_finished
        if finished:
            self._picker_finished.emit()
        return swallow

    def _on_picker_finished(self) -> None:
        picker = self._end_session()
        if picker is None:
            return  # already cancelled meanwhile
        if picker.phase is PickerPhase.COMPLETED:
            points: list[Point] = list(picker.points)
            log.info("Selection completed with %d points", len(points))
            self.completed.emit(picker.mode, points)
        else:
            self.cancelled.emit("Selection cancelled (right click).")
