from ocr_capture.geometry import Point
from ocr_capture.point_picker import MouseEvent, MouseEventKind, PickerPhase, PickMode, PointPicker

K = MouseEventKind


def feed(picker: PointPicker, *events: tuple[MouseEventKind, int, int]) -> list[bool]:
    return [picker.feed(MouseEvent(kind, Point(x, y))) for kind, x, y in events]


def test_rectangle_two_clicks():
    picker = PointPicker(PickMode.RECTANGLE)
    swallowed = feed(picker, (K.MOVE, 1, 1), (K.LEFT_DOWN, 10, 10), (K.LEFT_UP, 10, 10), (K.MOVE, 50, 50))
    assert swallowed == [False, True, True, False]
    assert picker.phase is PickerPhase.TRACING

    assert feed(picker, (K.LEFT_DOWN, 60, 40)) == [True]
    assert picker.phase is PickerPhase.FINISHING
    assert feed(picker, (K.LEFT_UP, 60, 40)) == [True]
    assert picker.phase is PickerPhase.COMPLETED
    assert picker.points == (Point(10, 10), Point(60, 40))
    assert feed(picker, (K.LEFT_DOWN, 0, 0)) == [False]


def test_freeform_records_path_with_min_distance():
    picker = PointPicker(PickMode.FREEFORM, min_point_distance=5)
    feed(
        picker,
        (K.LEFT_DOWN, 0, 0),
        (K.LEFT_UP, 0, 0),
        (K.MOVE, 1, 1),
        (K.MOVE, 10, 0),
        (K.MOVE, 10, 10),
        (K.LEFT_DOWN, 0, 10),
        (K.LEFT_UP, 0, 10),
    )
    assert picker.phase is PickerPhase.COMPLETED
    assert picker.points == (Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10))


def test_rectangle_ignores_moves():
    picker = PointPicker(PickMode.RECTANGLE)
    feed(picker, (K.LEFT_DOWN, 0, 0), (K.LEFT_UP, 0, 0), (K.MOVE, 5, 5), (K.LEFT_DOWN, 9, 9), (K.LEFT_UP, 9, 9))
    assert picker.points == (Point(0, 0), Point(9, 9))


def test_right_click_cancels_after_release():
    picker = PointPicker(PickMode.FREEFORM)
    feed(picker, (K.LEFT_DOWN, 0, 0), (K.LEFT_UP, 0, 0))
    assert feed(picker, (K.RIGHT_DOWN, 3, 3)) == [True]
    assert picker.phase is PickerPhase.FINISHING
    assert feed(picker, (K.RIGHT_UP, 3, 3)) == [True]
    assert picker.phase is PickerPhase.CANCELLED


def test_release_of_click_started_before_listening_is_not_swallowed():
    picker = PointPicker(PickMode.RECTANGLE)
    assert feed(picker, (K.LEFT_UP, 0, 0), (K.RIGHT_UP, 0, 0)) == [False, False]
    assert picker.phase is PickerPhase.WAITING_FOR_START


def test_drag_with_button_held_still_needs_second_click():
    picker = PointPicker(PickMode.FREEFORM)
    feed(picker, (K.LEFT_DOWN, 0, 0), (K.MOVE, 20, 0), (K.LEFT_UP, 20, 0))
    assert picker.phase is PickerPhase.TRACING
    feed(picker, (K.MOVE, 20, 20), (K.LEFT_DOWN, 0, 20), (K.LEFT_UP, 0, 20))
    assert picker.phase is PickerPhase.COMPLETED
    assert len(picker.points) == 4
