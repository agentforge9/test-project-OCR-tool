"""Screen geometry value types.

All coordinates are *physical* screen pixels (the same units Windows uses for
the mouse and for screenshots), so no DPI conversion is ever needed.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int

    def distance_to(self, other: Point) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True, slots=True)
class ScreenRect:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        """Exclusive right edge."""
        return self.left + self.width

    @property
    def bottom(self) -> int:
        """Exclusive bottom edge."""
        return self.top + self.height

    @property
    def origin(self) -> Point:
        return Point(self.left, self.top)

    @classmethod
    def from_corners(cls, a: Point, b: Point) -> ScreenRect:
        """Rectangle that includes both corner pixels, in any drag direction."""
        return cls.bounding((a, b))

    @classmethod
    def bounding(cls, points: Iterable[Point]) -> ScreenRect:
        """Smallest rectangle that includes every point."""
        pts = list(points)
        if not pts:
            raise ValueError("bounding() needs at least one point")
        left = min(p.x for p in pts)
        top = min(p.y for p in pts)
        right = max(p.x for p in pts)
        bottom = max(p.y for p in pts)
        return cls(left, top, right - left + 1, bottom - top + 1)

    def is_at_least(self, min_size: int) -> bool:
        return self.width >= min_size and self.height >= min_size

    def to_dict(self) -> dict[str, int]:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ScreenRect:
        """Build from settings.json data. Raises ValueError on bad input."""
        try:
            values = {key: data[key] for key in ("left", "top", "width", "height")}
        except (KeyError, TypeError) as exc:
            raise ValueError(f"region needs left, top, width and height: {exc}") from exc
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in values.values()):
            raise ValueError("region values must be whole numbers")
        if values["width"] <= 0 or values["height"] <= 0:
            raise ValueError("region width and height must be positive")
        return cls(**values)

    def __str__(self) -> str:
        return f"x={self.left}, y={self.top}, {self.width} x {self.height} px"
