"""Runs the real text pipeline (thread, signals, diff, clipboard) with a fake OCR."""

import os
import time

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication  # noqa: E402

from ocr_capture.capture_controller import CaptureController  # noqa: E402
from ocr_capture.config import HotkeyAction  # noqa: E402
from ocr_capture.geometry import ScreenRect  # noqa: E402
from ocr_capture.settings import AppSettings  # noqa: E402
from ocr_capture.text_layout import OcrLine, OcrWord  # noqa: E402

TIMEOUT_SECONDS = 5


class FakeRecognizer:
    def __init__(self, frames: list[list[str]]) -> None:
        self._frames = iter(frames)

    def recognize(self, _image):
        texts = next(self._frames)
        return [OcrLine((OcrWord(t, 0, i * 30, len(t) * 10, 20),)) for i, t in enumerate(texts)]


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def wait_for(qt_app, condition) -> None:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError
        qt_app.processEvents()
        time.sleep(0.01)


def test_text_capture_emits_only_new_text(qt_app):
    settings = AppSettings(region=ScreenRect(0, 0, 50, 50))
    recognizer = FakeRecognizer([["hello"], ["hello", "world"], ["hello", "world"]])
    controller = CaptureController(
        lambda: settings,
        recognizer_factory=lambda _ocr: recognizer,
        grab=lambda rect: Image.new("RGB", (rect.width, rect.height)),
    )
    captured: list[str] = []
    statuses: list[str] = []
    controller.text_captured.connect(captured.append)
    controller.status.connect(lambda message, _err: statuses.append(message))

    for expected_count in (1, 2):
        controller.handle_action(HotkeyAction.CAPTURE_NEW_TEXT)
        wait_for(qt_app, lambda: len(captured) == expected_count)
    controller.handle_action(HotkeyAction.CAPTURE_NEW_TEXT)
    wait_for(qt_app, lambda: "No new text." in statuses)

    assert captured == ["hello", "world"]
    assert qt_app.clipboard().text() == "world"
    controller.shutdown()


def test_text_capture_without_region_reports_error(qt_app):
    controller = CaptureController(lambda: AppSettings(), recognizer_factory=lambda _ocr: None)
    errors: list[str] = []
    controller.status.connect(lambda message, is_error: is_error and errors.append(message))
    controller.handle_action(HotkeyAction.CAPTURE_NEW_TEXT)
    assert errors and "region" in errors[0]
    controller.shutdown()
