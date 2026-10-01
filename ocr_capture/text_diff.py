"""Return only the *new* text between two OCR captures (live captioning).

How it works, in simple words:
1. The previous capture is remembered.
2. Both captures are split into lines and the lines are lined up with
   ``difflib`` (the same idea as ``git diff``). Lines that exist in both are
   skipped; lines that scrolled away at the top are ignored.
3. Lines that changed are looked at more closely:
   * the old line plus extra words at the end ("Hello" -> "Hello world")
     gives only the extra part ("world");
   * a line that is just a slightly different OCR reading of the old one
     ("He1lo world" vs "Hello world"), or only its beginning, gives nothing;
   * anything else is a completely new line and is returned whole.

Captions usually scroll up and grow at the bottom, which is exactly the case
this handles. Pure Python, fully unit-testable.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher

from . import config

_WORD = re.compile(r"\S+")


def _normalize(line: str) -> str:
    """Comparison key: case- and spacing-insensitive."""
    return " ".join(line.split()).casefold()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def _appended_part(old_line: str, new_line: str, threshold: float) -> str | None:
    """Words added to the end of ``old_line``.

    Returns the added text (``""`` if nothing was added) when ``new_line``
    starts with (a close OCR reading of) ``old_line``; otherwise ``None``.
    """
    old_words = old_line.split()
    new_matches = list(_WORD.finditer(new_line))
    if not old_words or len(new_matches) < len(old_words):
        return None
    new_head = " ".join(m.group() for m in new_matches[: len(old_words)])
    if _similarity(_normalize(" ".join(old_words)), _normalize(new_head)) < threshold:
        return None
    if len(new_matches) == len(old_words):
        return ""
    return new_line[new_matches[len(old_words)].start() :].rstrip()


def _new_part_of_line(line: str, candidates: Sequence[str], threshold: float) -> str | None:
    """What is new in ``line`` compared with the old lines it replaced."""
    if not line.strip():
        return None if any(not c.strip() for c in candidates) else ""

    filled = [c for c in candidates if c.strip()]
    for candidate in filled:
        appended = _appended_part(candidate, line, threshold)
        if appended is not None:
            return appended or None
    # The line is the beginning of an old line (captions re-wrapped): nothing new.
    if any(_appended_part(line, candidate, threshold) is not None for candidate in filled):
        return None
    key = _normalize(line)
    if any(_similarity(_normalize(c), key) >= threshold for c in filled):
        return None
    return line.rstrip()


def _trim_blank_edges(lines: list[str]) -> str:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def extract_new_text(
    previous: str,
    current: str,
    similarity_threshold: float = config.DEFAULT_TEXT_SIMILARITY_THRESHOLD,
) -> str:
    """Text in ``current`` that was not already in ``previous``."""
    if not previous.strip():
        return _trim_blank_edges(current.splitlines())

    previous_lines = previous.splitlines()
    current_lines = current.splitlines()
    matcher = SequenceMatcher(
        None,
        [_normalize(ln) for ln in previous_lines],
        [_normalize(ln) for ln in current_lines],
        autojunk=False,
    )

    new_pieces: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "delete"):
            continue
        candidates = previous_lines[i1:i2]
        for line in current_lines[j1:j2]:
            piece = _new_part_of_line(line, candidates, similarity_threshold)
            if piece is not None:
                new_pieces.append(piece)
    return _trim_blank_edges(new_pieces)


class NewTextTracker:
    """Remembers the last capture and returns only new text for each update.

    Not thread-safe: call it from one thread only (the UI thread).
    """

    def __init__(self, similarity_threshold: float = config.DEFAULT_TEXT_SIMILARITY_THRESHOLD) -> None:
        self.similarity_threshold = similarity_threshold
        self._previous = ""

    def update(self, current: str) -> str:
        new_text = extract_new_text(self._previous, current, self.similarity_threshold)
        # An empty capture (e.g. captions briefly hidden) keeps the memory, so
        # the same caption is not reported again when it reappears.
        if current.strip():
            self._previous = current
        return new_text

    def reset(self) -> None:
        self._previous = ""
