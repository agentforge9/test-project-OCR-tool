import pytest

from ocr_capture.text_diff import NewTextTracker, extract_new_text


def test_first_capture_returns_everything_with_layout():
    assert extract_new_text("", "\n  Hello   world\nsecond\n\n") == "  Hello   world\nsecond"


def test_identical_capture_returns_nothing():
    assert extract_new_text("a b\nc d", "a b\nc d") == ""


def test_new_line_at_bottom():
    assert extract_new_text("line one", "line one\nline two") == "line two"


def test_growing_line_returns_only_added_words():
    assert extract_new_text("I went to", "I went to the   store") == "the   store"


def test_scrolling_captions():
    previous = "I went to the store\nand bought"
    current = "and bought milk\nand some bread"
    assert extract_new_text(previous, current) == "milk\nand some bread"


def test_ocr_noise_is_not_reported_as_new():
    assert extract_new_text("Hello world, how are you", "He1lo world, how are you") == ""


def test_completely_different_text():
    assert extract_new_text("first caption", "totally unrelated words") == "totally unrelated words"


def test_shrinking_line_returns_nothing():
    assert extract_new_text("one two three", "one two") == ""


@pytest.mark.parametrize("threshold", [0.6, 0.8, 0.95])
def test_threshold_is_respected(threshold):
    result = extract_new_text("abcdefghij", "abcdefgxyz", similarity_threshold=threshold)
    assert result == ("" if threshold <= 0.7 else "abcdefgxyz")


def test_tracker_keeps_memory_through_empty_capture():
    tracker = NewTextTracker()
    assert tracker.update("hello") == "hello"
    assert tracker.update("") == ""
    assert tracker.update("hello") == ""
    assert tracker.update("hello there") == "there"
    tracker.reset()
    assert tracker.update("hello there") == "hello there"
