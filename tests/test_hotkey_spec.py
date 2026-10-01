import pytest

from ocr_capture.config import DEFAULT_HOTKEYS
from ocr_capture.hotkey_spec import (
    HotkeyError,
    HotkeySpec,
    Modifier,
    format_modifiers,
    key_name_for_code,
    parse_bindings,
    parse_optional,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Alt+Comma", "Alt+Comma"),
        ("alt + ,", "Alt+Comma"),
        ("Shift+Alt+/", "Alt+Shift+Slash"),
        ("win+ctrl+a", "Ctrl+Win+A"),
        ("Alt+.", "Alt+Period"),
        ("Alt+Decimal", "Alt+Decimal"),
        ("F9", "F9"),
        ("Control+Numpad5", "Ctrl+Numpad5"),
    ],
)
def test_parse_produces_canonical_text(text, expected):
    assert str(HotkeySpec.parse(text)) == expected


def test_virtual_keys_match_windows_codes():
    spec = HotkeySpec.parse("Alt+Shift+Slash")
    assert spec.virtual_key == 0xBF
    assert spec.modifiers == Modifier.ALT | Modifier.SHIFT
    assert int(spec.modifiers) == 0x0001 | 0x0004


@pytest.mark.parametrize(
    "text",
    ["", "Alt+", "Alt", "Alt+Alt+A", "Hyper+A", "Alt+NoSuchKey", "A", "Shift+A", "Alt++"],
)
def test_invalid_hotkeys_are_rejected(text):
    with pytest.raises(HotkeyError):
        HotkeySpec.parse(text)


def test_parse_optional_allows_empty():
    assert parse_optional("  ") is None


def test_defaults_are_valid_and_unique():
    bindings = parse_bindings({a.value: t for a, t in DEFAULT_HOTKEYS.items()})
    assert len(bindings) == len(DEFAULT_HOTKEYS)


def test_parse_bindings_rejects_duplicates_and_skips_empty():
    with pytest.raises(HotkeyError, match="used by both"):
        parse_bindings({"a": "Alt+X", "b": "alt+x"})
    assert set(parse_bindings({"a": "Alt+X", "b": ""})) == {"a"}


def test_key_name_lookup_and_modifier_preview():
    assert key_name_for_code(0xBC) == "Comma"
    assert key_name_for_code(0xFF) is None
    assert format_modifiers(Modifier.SHIFT | Modifier.ALT) == "Alt+Shift+"
