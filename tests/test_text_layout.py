from ocr_capture.text_layout import LayoutOptions, OcrLine, OcrWord, build_text

CHAR_W = 10
SPACE_W = 6
LINE_H = 20


def line(y: float, *words: tuple[str, float]) -> OcrLine:
    return OcrLine(tuple(OcrWord(text, x, y, len(text) * CHAR_W, LINE_H) for text, x in words))


def after(previous_x: float, previous_text: str, spaces: int) -> float:
    return previous_x + len(previous_text) * CHAR_W + spaces * SPACE_W


def test_empty_input():
    assert build_text([]) == ""


def test_single_spaces_and_wide_gaps_are_kept():
    lines = [
        line(0, ("one", 0), ("two", after(0, "one", 1)), ("three", after(after(0, "one", 1), "two", 1))),
        line(30, ("a", 0), ("b", after(0, "a", 1)), ("far", after(after(0, "a", 1), "b", 4))),
    ]
    assert build_text(lines) == "one two three\na b    far"


PITCH = 25


def test_indentation_and_one_blank_line():
    lines = [
        line(0, ("def", 0), ("f():", after(0, "def", 1)), ("x", 200)),
        line(PITCH, ("return", 4 * SPACE_W), ("1", after(4 * SPACE_W, "return", 1))),
        line(3 * PITCH, ("end", 0), ("of", after(0, "end", 1)), ("it", 300)),
    ]
    rows = build_text(lines).split("\n")
    assert len(rows) == 4
    assert rows[1] == "    return 1"
    assert rows[2] == ""
    assert rows[3].startswith("end of")


def test_no_blank_lines_for_normal_spacing():
    lines = [line(i * PITCH, ("row", 0), ("text", after(0, "row", 1))) for i in range(4)]
    assert build_text(lines) == "\n".join(["row text"] * 4)


def test_same_height_lines_merge_into_one_row():
    lines = [line(0, ("Name", 0)), line(1, ("Value", 300)), line(30, ("x", 0), ("y", after(0, "x", 1)), ("z", 100))]
    first_row = build_text(lines).split("\n")[0]
    assert first_row.startswith("Name ")
    assert first_row.endswith("Value")
    assert first_row.count(" ") > 5


def test_plain_mode_joins_with_single_spaces():
    lines = [line(0, ("a", 0), ("b", 300))]
    assert build_text(lines, LayoutOptions(preserve_layout=False)) == "a b"
