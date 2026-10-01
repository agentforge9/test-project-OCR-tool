"""Find the *new* words in a live-caption area (pure Python, unit-testable).

How it works, in simple words:
* Captions are a moving window over one long stream of words: old words
  scroll away at the top, new words appear at the end, and the caption
  engine sometimes corrects its last few words.
* So we compare *words*, not lines (lines re-wrap all the time). Each new
  screen is lined up against the previous screen with ``difflib``.
* The last solid overlap (the "anchor") marks where the old text ends.
  Every word after it is new.
* Words at the end of the previous screen that are not in the new screen
  were corrected by the caption engine. They are "retracted": if they are
  still waiting in the unsent buffer, they are removed, so the corrected
  words are not sent twice.
* ``CaptionTracker`` keeps the previous screen and the unsent buffer.
  ``take_pending`` hands out everything new since the last call.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from . import config

_NON_WORD = re.compile(r"[^\w]+")
WORD_SEPARATOR = " "


def _word_key(word: str) -> str:
    """Comparison key: ignores case and punctuation ("And." == "and")."""
    key = _NON_WORD.sub("", word.casefold())
    return key or word


@dataclass(frozen=True, slots=True)
class CaptionUpdate:
    new_words: tuple[str, ...]
    # How many of the most recent previous words were corrected or removed.
    retracted: int = 0


def diff_caption_words(
    previous: Sequence[str],
    current: Sequence[str],
    min_anchor_words: int = config.CAPTION_MIN_ANCHOR_WORDS,
    max_gap_words: int = config.CAPTION_MAX_GAP_WORDS,
) -> CaptionUpdate:
    """Words in ``current`` that come after the text already seen in ``previous``."""
    if not previous:
        return CaptionUpdate(tuple(current))

    blocks = [
        b
        for b in SequenceMatcher(
            None, [_word_key(w) for w in previous], [_word_key(w) for w in current], autojunk=False
        ).get_matching_blocks()
        if b.size
    ]
    required = min(min_anchor_words, len(previous))
    anchors = [b for b in blocks if b.size >= required]
    if not anchors:
        # No real overlap (only chance matches like "the"): a whole new screen.
        return CaptionUpdate(tuple(current))

    anchor = anchors[-1]
    end_prev, end_cur = anchor.a + anchor.size, anchor.b + anchor.size
    # Small matches shortly after the anchor are the same text with a word
    # or two corrected/misread in between; extend the anchor over them.
    for block in blocks[blocks.index(anchor) + 1 :]:
        if block.a - end_prev > max_gap_words or block.b - end_cur > max_gap_words:
            break
        end_prev, end_cur = block.a + block.size, block.b + block.size

    return CaptionUpdate(tuple(current[end_cur:]), retracted=len(previous) - end_prev)


class CaptionTracker:
    """Remembers the previous screen and collects unsent new words.

    After ``reset`` nothing has been sent yet, so the first screen is new in
    full: the first take returns all text in the region, later takes only
    what appeared since. Not thread-safe: use from one thread.
    """

    def __init__(
        self,
        min_anchor_words: int = config.CAPTION_MIN_ANCHOR_WORDS,
        max_gap_words: int = config.CAPTION_MAX_GAP_WORDS,
    ) -> None:
        self._min_anchor_words = min_anchor_words
        self._max_gap_words = max_gap_words
        self._previous: tuple[str, ...] | None = None
        self._pending: list[str] = []

    @property
    def pending_text(self) -> str:
        return WORD_SEPARATOR.join(self._pending)

    def observe(self, words: Sequence[str]) -> CaptionUpdate:
        """Feed one capture. Returns what changed (already applied to the buffer)."""
        if not words:
            # Captions briefly hidden: keep the memory so nothing repeats later.
            return CaptionUpdate(())

        update = diff_caption_words(self._previous or (), words, self._min_anchor_words, self._max_gap_words)
        if update.retracted:
            del self._pending[max(0, len(self._pending) - update.retracted) :]
        self._pending.extend(update.new_words)
        self._previous = tuple(words)
        return update

    def take_pending(self) -> str:
        """All new words since the last call (empty string if none)."""
        text = self.pending_text
        self._pending.clear()
        return text

    def reset(self) -> None:
        """Forget everything; the next screen counts as new in full."""
        self._previous = None
        self._pending.clear()
