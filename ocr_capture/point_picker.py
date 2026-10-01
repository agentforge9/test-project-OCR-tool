"""State machine for picking screen points with plain mouse clicks.

Used by the two silent image hotkeys. Nothing is drawn on screen; we only
listen to the mouse (see ``win32/mouse_hook.py``) and feed every event here.

Rectangle mode:  click start point -> click end point -> done.
Freeform mode:   click start point -> move the mouse along any path
                 -> click again -> done (the path is closed back to start).
Right click at any time cancels.

The clicks we use are *swallowed* (not passed to the window under the
mouse), so picking points never clicks buttons in other programs. Mouse
movement is never swallowed, so the cursor always moves normally.

Pure Python, no Win32 or Qt: fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .geometry import Point


class MouseEventKind(Enum):
    MOVE = auto()
    LEFT_DOWN = auto()
    LEFT_UP = auto()
    RIGHT_DOWN = auto()
    RIGHT_UP = auto()


@dataclass(frozen=True, slots=True)
class MouseEvent:
    kind: MouseEventKind
    point: Point


class PickMode(Enum):
    RECTANGLE = "rectangle"
    FREEFORM = "freeform"


class PickerPhase(Enum):
    WAITING_FOR_START = auto()
    TRACING = auto()
    # Result is known; waiting for the button release so it can be swallowed
    # too (a lone "button up" could confuse the program under the mouse).
    FINISHING = auto()
    COMPLETED = auto()
    CANCELLED = auto()


class PointPicker:
    def __init__(self, mode: PickMode, min_point_distance: float = 0.0) -> None:
        self.mode = mode
        self._min_point_distance = min_point_distance
        self._phase = PickerPhase.WAITING_FOR_START
        self._points: list[Point] = []
        self._cancel_requested = False
        self._left_up_pending = False
        self._right_up_pending = False

    @property
    def phase(self) -> PickerPhase:
        return self._phase

    @property
    def is_finished(self) -> bool:
        return self._phase in (PickerPhase.COMPLETED, PickerPhase.CANCELLED)

    @property
    def points(self) -> tuple[Point, ...]:
        return tuple(self._points)

    def feed(self, event: MouseEvent) -> bool:
        """Process one mouse event. Returns True if it must be swallowed."""
        if self.is_finished:
            return False
        handler = {
            MouseEventKind.MOVE: self._on_move,
            MouseEventKind.LEFT_DOWN: self._on_left_down,
            MouseEventKind.LEFT_UP: self._on_left_up,
            MouseEventKind.RIGHT_DOWN: self._on_right_down,
            MouseEventKind.RIGHT_UP: self._on_right_up,
        }[event.kind]
        return handler(event.point)

    def _on_move(self, point: Point) -> bool:
        if self._phase is PickerPhase.TRACING and self.mode is PickMode.FREEFORM:
            if self._points[-1].distance_to(point) >= self._min_point_distance:
                self._points.append(point)
        return False

    def _on_left_down(self, point: Point) -> bool:
        if self._phase is PickerPhase.WAITING_FOR_START:
            self._points = [point]
            self._phase = PickerPhase.TRACING
        elif self._phase is PickerPhase.TRACING:
            if self._points[-1] != point:
                self._points.append(point)
            self._phase = PickerPhase.FINISHING
        self._left_up_pending = True
        return True

    def _on_left_up(self, _point: Point) -> bool:
        if not self._left_up_pending:
            return False  # its "down" happened before we started listening
        self._left_up_pending = False
        self._finish_if_released()
        return True

    def _on_right_down(self, _point: Point) -> bool:
        self._cancel_requested = True
        self._phase = PickerPhase.FINISHING
        self._right_up_pending = True
        return True

    def _on_right_up(self, _point: Point) -> bool:
        if not self._right_up_pending:
            return False
        self._right_up_pending = False
        self._finish_if_released()
        return True

    def _finish_if_released(self) -> None:
        if self._phase is not PickerPhase.FINISHING or self._left_up_pending or self._right_up_pending:
            return
        self._phase = PickerPhase.CANCELLED if self._cancel_requested else PickerPhase.COMPLETED
