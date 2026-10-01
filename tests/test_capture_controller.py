"""Runs the real caption pipeline (thread, signals, tracker, clipboard) with a fake OCR.

Auto paste is turned off here so the tests never send keystrokes.
"""

import os
import time
from dataclasses import replace

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from ocr_capture.capture_controller import CaptureController  # noqa: E402
from ocr_capture.config import HotkeyAction  # noqa: E402
from ocr_capture.geometry import ScreenRect  # noqa: E402
from ocr_capture.settings import AppSettings, TextCaptureSettings  # noqa: E402
from ocr_capture.text_layout import OcrLine, OcrWord  # noqa: E402

TIMEOUT_SECONDS = 5
SETTLE_SECONDS = 0.3
CLIPBOARD_SENTINEL = "untouched"


class FakeScreen:
    """Recognizer whose visible caption the test changes between reads."""

    def __init__(self) -> None:
        self.caption = ""
        self.reads = 0

    def recognize(self, _image):
        self.reads += 1
        return [OcrLine(tuple(OcrWord(w, i * 50, 0, 40, 20) for i, w in enumerate(self.caption.split())))]


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def pump(qt_app, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qt_app.processEvents()
        time.sleep(0.01)


def wait_for(qt_app, condition) -> None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError
        pump(qt_app, 0.01)


def make_controller(screen: FakeScreen, poll_interval_ms: int) -> tuple[CaptureController, list[str], list[str]]:
    text = replace(TextCaptureSettings(), poll_interval_ms=poll_interval_ms, auto_paste=False, paste_separator="")
    settings = AppSettings(region=ScreenRect(0, 0, 50, 50), text_capture=text)
    controller = CaptureController(
        lambda: settings,
        recognizer_factory=lambda _ocr: screen,
        grab=lambda rect: Image.new("RGB", (rect.width, rect.height)),
    )
    delivered: list[str] = []
    statuses: list[str] = []
    controller.text_delivered.connect(delivered.append)
    controller.status.connect(lambda message, _err: statuses.append(message))
    return controller, delivered, statuses


NOTHING_NEW_STATUS = "No new text since the last paste. Nothing pasted."


def test_first_press_delivers_all_text_then_only_new_text(qt_app):
    screen = FakeScreen()
    screen.caption = "already visible text"
    controller, delivered, statuses = make_controller(screen, poll_interval_ms=0)
    controller.activate()

    controller.handle_action(HotkeyAction.CAPTURE_NEW_TEXT)
    wait_for(qt_app, lambda: len(delivered) == 1)
    assert delivered == ["already visible text"]

    qt_app.clipboard().setText(CLIPBOARD_SENTINEL)
    controller.handle_action(HotkeyAction.CAPTURE_NEW_TEXT)
    wait_for(qt_app, lambda: NOTHING_NEW_STATUS in statuses)
    assert len(delivered) == 1
    assert qt_app.clipboard().text() == CLIPBOARD_SENTINEL

    screen.caption = "already visible text and now more words"
    controller.handle_action(HotkeyAction.CAPTURE_NEW_TEXT)
    wait_for(qt_app, lambda: len(delivered) == 2)
    assert delivered[1] == "and now more words"
    assert qt_app.clipboard().text() == "and now more words"
    controller.shutdown()


def test_empty_region_reports_no_text(qt_app):
    screen = FakeScreen()
    controller, delivered, statuses = make_controller(screen, poll_interval_ms=0)
    controller.activate()
    controller.handle_action(HotkeyAction.CAPTURE_NEW_TEXT)
    wait_for(qt_app, lambda: any(s.startswith("No text found") for s in statuses))
    assert delivered == []
    controller.shutdown()


def test_background_polling_keeps_words_that_scrolled_away(qt_app):
    screen = FakeScreen()
    screen.caption = "one two three"
    controller, delivered, _ = make_controller(screen, poll_interval_ms=200)
    controller.activate()
    wait_for(qt_app, lambda: screen.reads >= 1)

    screen.caption = "one two three four five"
    wait_for(qt_app, lambda: screen.reads >= 3)
    screen.caption = "four five six seven"  # "four five" scrolled to the top
    wait_for(qt_app, lambda: screen.reads >= 5)
    screen.caption = "eight nine"  # everything before scrolled away
    pump(qt_app, SETTLE_SECONDS)

    controller.handle_action(HotkeyAction.CAPTURE_NEW_TEXT)
    wait_for(qt_app, lambda: len(delivered) == 1)
    assert delivered == ["one two three four five six seven eight nine"]
    controller.shutdown()


def test_capture_without_region_reports_error(qt_app):
    controller = CaptureController(lambda: AppSettings(), recognizer_factory=lambda _ocr: None)
    errors: list[str] = []
    controller.status.connect(lambda message, is_error: is_error and errors.append(message))
    controller.handle_action(HotkeyAction.CAPTURE_NEW_TEXT)
    assert errors and "region" in errors[0]
    controller.shutdown()
