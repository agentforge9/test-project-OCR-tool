"""Keyboard helpers for auto paste: key state, focused window, Ctrl+V."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from . import api

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_V = 0x56
# An unassigned virtual key: pressing it does nothing in any program.
VK_UNASSIGNED = 0xE8
_MODIFIER_KEYS = (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)
_MENU_MODIFIER_KEYS = (VK_MENU, VK_LWIN, VK_RWIN)
_KEY_DOWN_BIT = 0x8000


def modifiers_held() -> bool:
    """True while Shift, Ctrl, Alt or Win is physically pressed."""
    return any(api.user32.GetAsyncKeyState(vk) & _KEY_DOWN_BIT for vk in _MODIFIER_KEYS)


def foreground_is_own_window() -> bool:
    """True if one of this app's windows has the keyboard focus."""
    hwnd = api.user32.GetForegroundWindow()
    if not hwnd:
        return False
    pid = wintypes.DWORD()
    api.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()


def _key(vk: int, key_up: bool) -> api.INPUT:
    event = api.INPUT(type=api.INPUT_KEYBOARD)
    event.union.ki = api.KEYBDINPUT(wVk=vk, dwFlags=api.KEYEVENTF_KEYUP if key_up else 0)
    return event


def mask_menu_key_release() -> None:
    """Stop a held Alt/Win from opening the menu bar / Start menu on release.

    Windows swallows the hotkey's main key, so the focused program sees Alt
    (or Win) pressed and released alone, which moves focus to its menu bar
    (or opens Start), and a later Ctrl+V would land there. Pressing an
    unassigned key while the modifier is still down prevents that.
    """
    if not any(api.user32.GetAsyncKeyState(vk) & _KEY_DOWN_BIT for vk in _MENU_MODIFIER_KEYS):
        return
    events = (api.INPUT * 2)(_key(VK_UNASSIGNED, False), _key(VK_UNASSIGNED, True))
    api.user32.SendInput(len(events), events, ctypes.sizeof(api.INPUT))


def send_ctrl_v() -> None:
    """Press Ctrl+V in the focused window. Raises OSError if Windows blocks it."""
    events = (api.INPUT * 4)(
        _key(VK_CONTROL, False),
        _key(VK_V, False),
        _key(VK_V, True),
        _key(VK_CONTROL, True),
    )
    sent = api.user32.SendInput(len(events), events, ctypes.sizeof(api.INPUT))
    if sent != len(events):
        raise OSError(f"Windows blocked the paste keystroke: {api.last_error_message()}")
