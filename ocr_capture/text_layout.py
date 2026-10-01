"""Rebuild readable text, with spacing and line breaks, from OCR word boxes.

OCR engines return words with pixel positions, and join each line's words
with a single space. To keep the original look (indentation, column gaps,
empty lines) we convert pixel gaps back into spaces and empty lines:

* Space width is measured from the capture itself: the most common gap
  between neighbouring words is one space. This works for both proportional
  and monospaced fonts.
* Lines at the same height (for example table columns that OCR returned as
  separate lines) are merged into one row.
* A large vertical gap between rows becomes one or more empty lines.

Pure Python, no OCR or Qt dependency, so it is fully unit-testable.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from . import config


@dataclass(frozen=True, slots=True)
class OcrWord:
    text: str
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def center_y(self) -> float:
        return self.top + self.height / 2


@dataclass(frozen=True, slots=True)
class OcrLine:
    words: tuple[OcrWord, ...]

    @property
    def top(self) -> float:
        return min(w.top for w in self.words)

    @property
    def bottom(self) -> float:
        return max(w.bottom for w in self.words)

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2

    def plain_text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass(frozen=True, slots=True)
class LayoutOptions:
    preserve_layout: bool = config.DEFAULT_PRESERVE_LAYOUT
    row_merge_ratio: float = config.LAYOUT_ROW_MERGE_RATIO
    fallback_line_pitch_ratio: float = config.LAYOUT_FALLBACK_LINE_PITCH_RATIO
    min_row_gaps_for_pitch_calibration: int = config.LAYOUT_MIN_ROW_GAPS_FOR_PITCH_CALIBRATION
    max_blank_lines: int = config.LAYOUT_MAX_BLANK_LINES
    max_spaces_between_words: int = config.LAYOUT_MAX_SPACES_BETWEEN_WORDS
    max_indent_spaces: int = config.LAYOUT_MAX_INDENT_SPACES
    fallback_space_width_ratio: float = config.LAYOUT_FALLBACK_SPACE_WIDTH_RATIO
    min_gaps_for_space_calibration: int = config.LAYOUT_MIN_GAPS_FOR_SPACE_CALIBRATION


def build_text(lines: Sequence[OcrLine], options: LayoutOptions = LayoutOptions()) -> str:
    """Turn OCR lines into text. Empty input gives an empty string."""
    lines = [line for line in lines if line.words]
    if not lines:
        return ""
    if not options.preserve_layout:
        return "\n".join(line.plain_text() for line in lines)

    all_words = [w for line in lines for w in line.words]
    line_height = statistics.median(w.height for w in all_words) or 1.0
    space_width = _estimate_space_width(lines, options)
    origin_x = min(w.left for w in all_words)

    rows = _group_into_rows(lines, line_height * options.row_merge_ratio)
    centres = [statistics.fmean(w.center_y for w in row) for row in rows]
    distances = [b - a for a, b in zip(centres, centres[1:])]
    pitch = _estimate_line_pitch(distances, line_height, options)

    output = [_render_row(rows[0], origin_x, space_width, options)]
    for row, distance in zip(rows[1:], distances):
        blank_lines = round(distance / pitch) - 1
        output.extend([""] * max(0, min(blank_lines, options.max_blank_lines)))
        output.append(_render_row(row, origin_x, space_width, options))
    return "\n".join(output)


def _lower_half_median(values: Sequence[float]) -> float:
    """Typical *small* value: ignores the large outliers (column gaps, empty lines)."""
    ordered = sorted(values)
    return statistics.median(ordered[: max(1, len(ordered) // 2)])


def _estimate_line_pitch(distances: Sequence[float], line_height: float, options: LayoutOptions) -> float:
    if len(distances) >= options.min_row_gaps_for_pitch_calibration:
        return max(1.0, _lower_half_median(distances))
    return max(1.0, line_height * options.fallback_line_pitch_ratio)


def _estimate_space_width(lines: Sequence[OcrLine], options: LayoutOptions) -> float:
    gaps: list[float] = []
    for line in lines:
        ordered = sorted(line.words, key=lambda w: w.left)
        gaps.extend(b.left - a.right for a, b in zip(ordered, ordered[1:]) if b.left > a.right)
    if len(gaps) >= options.min_gaps_for_space_calibration:
        return max(1.0, _lower_half_median(gaps))

    char_widths = [w.width / len(w.text) for line in lines for w in line.words if w.text]
    average_char_width = statistics.median(char_widths) if char_widths else 1.0
    return max(1.0, average_char_width * options.fallback_space_width_ratio)


def _group_into_rows(lines: Sequence[OcrLine], merge_distance: float) -> list[list[OcrWord]]:
    """Group lines whose vertical centres are close; rows sorted top to bottom."""
    rows: list[tuple[float, list[OcrWord]]] = []
    for line in sorted(lines, key=lambda ln: ln.center_y):
        if rows and abs(line.center_y - rows[-1][0]) <= merge_distance:
            rows[-1][1].extend(line.words)
        else:
            rows.append((line.center_y, list(line.words)))
    return [sorted(words, key=lambda w: w.left) for _, words in rows]


def _render_row(words: Sequence[OcrWord], origin_x: float, space_width: float, options: LayoutOptions) -> str:
    indent = min(options.max_indent_spaces, round((words[0].left - origin_x) / space_width))
    parts = [" " * max(0, indent), words[0].text]
    for previous, word in zip(words, words[1:]):
        spaces = round((word.left - previous.right) / space_width)
        parts.append(" " * max(1, min(spaces, options.max_spaces_between_words)))
        parts.append(word.text)
    return "".join(parts)
