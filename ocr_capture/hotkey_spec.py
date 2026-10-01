"""Parse, validate and format hotkey text such as ``Alt+Shift+Slash``.

This module is pure Python (no Qt, no Win32 calls) so it is easy to test.
The same canonical text is used in the UI, in settings.json and in logs:
modifiers in the order Ctrl, Alt, Shift, Win, then exactly one key.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntFlag


class HotkeyError(ValueError):
    """Raised for hotkey text that cannot be used. The message is user-facing."""


class Modifier(IntFlag):
    """Values are the Win32 ``MOD_*`` flags expected by ``RegisterHotKey``."""

    NONE = 0x0000
    ALT = 0x0001
    CTRL = 0x0002
    SHIFT = 0x0004
    WIN = 0x0008


MODIFIER_ORDER: tuple[Modifier, ...] = (Modifier.CTRL, Modifier.ALT, Modifier.SHIFT, Modifier.WIN)
MODIFIER_NAMES: dict[Modifier, str] = {
    Modifier.CTRL: "Ctrl",
    Modifier.ALT: "Alt",
    Modifier.SHIFT: "Shift",
    Modifier.WIN: "Win",
}
_MODIFIER_ALIASES: dict[str, Modifier] = {
    "ctrl": Modifier.CTRL,
    "control": Modifier.CTRL,
    "alt": Modifier.ALT,
    "shift": Modifier.SHIFT,
    "win": Modifier.WIN,
    "windows": Modifier.WIN,
    "meta": Modifier.WIN,
}


def _build_key_table() -> dict[str, int]:
    """Canonical key name -> Windows virtual-key code."""
    keys: dict[str, int] = {}
    keys.update({chr(c): c for c in range(ord("A"), ord("Z") + 1)})
    keys.update({str(d): ord(str(d)) for d in range(10)})
    keys.update({f"F{n}": 0x70 + n - 1 for n in range(1, 25)})
    keys.update({f"Numpad{n}": 0x60 + n for n in range(10)})
    keys.update(
        {
            "Backspace": 0x08,
            "Tab": 0x09,
            "Enter": 0x0D,
            "Pause": 0x13,
            "Escape": 0x1B,
            "Space": 0x20,
            "PageUp": 0x21,
            "PageDown": 0x22,
            "End": 0x23,
            "Home": 0x24,
            "Left": 0x25,
            "Up": 0x26,
            "Right": 0x27,
            "Down": 0x28,
            "PrintScreen": 0x2C,
            "Insert": 0x2D,
            "Delete": 0x2E,
            "Multiply": 0x6A,
            "Add": 0x6B,
            "Subtract": 0x6D,
            "Decimal": 0x6E,  # the "." key on the number pad
            "Divide": 0x6F,
            "Semicolon": 0xBA,
            "Equals": 0xBB,
            "Comma": 0xBC,
            "Minus": 0xBD,
            "Period": 0xBE,  # the "." key next to "," on the main keyboard
            "Slash": 0xBF,
            "Backtick": 0xC0,
            "LeftBracket": 0xDB,
            "Backslash": 0xDC,
            "RightBracket": 0xDD,
            "Quote": 0xDE,
        }
    )
    return keys


KEY_CODES: dict[str, int] = _build_key_table()
_KEY_NAMES_BY_CODE: dict[int, str] = {code: name for name, code in KEY_CODES.items()}

_KEY_ALIASES: dict[str, str] = {
    ",": "Comma",
    ".": "Period",
    "dot": "Period",
    "/": "Slash",
    ";": "Semicolon",
    "=": "Equals",
    "-": "Minus",
    "`": "Backtick",
    "[": "LeftBracket",
    "]": "RightBracket",
    "\\": "Backslash",
    "'": "Quote",
    "esc": "Escape",
    "return": "Enter",
    "del": "Delete",
    "ins": "Insert",
    "pgup": "PageUp",
    "pgdn": "PageDown",
    "numpaddot": "Decimal",
    "numpaddecimal": "Decimal",
}
_KEY_LOOKUP: dict[str, str] = {name.lower(): name for name in KEY_CODES} | _KEY_ALIASES

# Keys that never produce text, so they are safe as hotkeys on their own.
# Every other key needs Ctrl, Alt or Win, or normal typing would be hijacked.
KEYS_ALLOWED_WITHOUT_MODIFIER: frozenset[str] = frozenset(
    {f"F{n}" for n in range(1, 25)} | {"Pause"}
)
_TYPING_SAFE_MODIFIERS = Modifier.CTRL | Modifier.ALT | Modifier.WIN

# Windows virtual-key codes of the modifier keys themselves (both sides).
MODIFIER_KEY_CODES: frozenset[int] = frozenset(
    {0x10, 0x11, 0x12, 0x5B, 0x5C, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5}
)

SEPARATOR = "+"


@dataclass(frozen=True, slots=True)
class HotkeySpec:
    """One validated hotkey: a set of modifiers plus exactly one key."""

    modifiers: Modifier
    key: str

    def __post_init__(self) -> None:
        if self.key not in KEY_CODES:
            raise HotkeyError(f"Unknown key '{self.key}'.")
        if not self.modifiers & _TYPING_SAFE_MODIFIERS and self.key not in KEYS_ALLOWED_WITHOUT_MODIFIER:
            raise HotkeyError(
                f"'{self}' would block normal typing. Add Ctrl, Alt or Win "
                f"(only F1-F24 and Pause may be used alone)."
            )

    @property
    def virtual_key(self) -> int:
        return KEY_CODES[self.key]

    @classmethod
    def parse(cls, text: str) -> HotkeySpec:
        """Parse user text (case-insensitive, aliases allowed). Raises HotkeyError."""
        parts = [part.strip() for part in text.split(SEPARATOR)]
        if not text.strip() or any(not part for part in parts):
            raise HotkeyError(f"'{text}' is not a valid hotkey. Example: Alt+Shift+Slash")

        *modifier_parts, key_part = parts
        modifiers = Modifier.NONE
        for part in modifier_parts:
            modifier = _MODIFIER_ALIASES.get(part.lower())
            if modifier is None:
                raise HotkeyError(f"'{part}' is not a modifier. Use Ctrl, Alt, Shift or Win.")
            if modifiers & modifier:
                raise HotkeyError(f"'{part}' is used twice in '{text}'.")
            modifiers |= modifier

        if key_part.lower() in _MODIFIER_ALIASES:
            raise HotkeyError(f"'{text}' has no main key. Add a key such as A, F5 or Slash.")
        key = _KEY_LOOKUP.get(key_part.lower())
        if key is None:
            raise HotkeyError(f"'{key_part}' is not a supported key.")
        return cls(modifiers, key)

    def __str__(self) -> str:
        names = [MODIFIER_NAMES[m] for m in MODIFIER_ORDER if self.modifiers & m]
        return SEPARATOR.join([*names, self.key])


def parse_optional(text: str) -> HotkeySpec | None:
    """Like ``HotkeySpec.parse`` but an empty text means "no hotkey"."""
    return HotkeySpec.parse(text) if text.strip() else None


def parse_bindings(hotkeys: Mapping[str, str]) -> dict[str, HotkeySpec]:
    """Parse action -> hotkey text. Empty texts are skipped (action disabled).

    Raises HotkeyError if a text is invalid or two actions share a hotkey.
    """
    bindings: dict[str, HotkeySpec] = {}
    owner_by_spec: dict[HotkeySpec, str] = {}
    for action, text in hotkeys.items():
        try:
            spec = parse_optional(text)
        except HotkeyError as exc:
            raise HotkeyError(f"{action}: {exc}") from exc
        if spec is None:
            continue
        if spec in owner_by_spec:
            raise HotkeyError(f"'{spec}' is used by both {owner_by_spec[spec]} and {action}.")
        owner_by_spec[spec] = action
        bindings[action] = spec
    return bindings


def key_name_for_code(virtual_key: int) -> str | None:
    """Canonical name for a Windows virtual-key code, or None if unsupported."""
    return _KEY_NAMES_BY_CODE.get(virtual_key)


def format_modifiers(modifiers: Modifier) -> str:
    """e.g. ``Ctrl+Alt+`` - used to preview a hotkey while keys are held."""
    names = [MODIFIER_NAMES[m] for m in MODIFIER_ORDER if modifiers & m]
    return "".join(f"{name}{SEPARATOR}" for name in names)
