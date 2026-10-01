"""Low-level global mouse hook running on its own thread.

Windows calls a low-level hook for *every* mouse event in the system and
waits for the answer. If the hook is slow, the whole mouse lags (and Windows
silently removes slow hooks). Therefore:

* the hook runs on a dedicated thread with its own message loop, never on
  the busy UI thread;
* the handler must be fast and must only return "swallow or not";
* the hook is installed only while a selection is in progress.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from collections.abc import Callable
from ctypes import wintypes

from .. import config
from ..geometry import Point
from ..point_picker import MouseEvent, MouseEventKind
from . import api

log = logging.getLogger(__name__)

MouseHandler = Callable[[MouseEvent], bool]
"""Receives each mouse event; returns True to swallow (block) it."""

_KINDS_BY_MESSAGE = {
    api.WM_MOUSEMOVE: MouseEventKind.MOVE,
    api.WM_LBUTTONDOWN: MouseEventKind.LEFT_DOWN,
    api.WM_LBUTTONUP: MouseEventKind.LEFT_UP,
    api.WM_RBUTTONDOWN: MouseEventKind.RIGHT_DOWN,
    api.WM_RBUTTONUP: MouseEventKind.RIGHT_UP,
}
_SWALLOW = 1


class MouseHookError(RuntimeError):
    """The hook could not be installed. The message is user-facing."""


class LowLevelMouseHook:
    def __init__(self, handler: MouseHandler) -> None:
        self._handler = handler
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self._start_error: str | None = None
        # Keep a reference: if the ctypes callback is garbage-collected while
        # the hook is installed, Windows calls freed memory and the app crashes.
        self._proc = api.LowLevelMouseProc(self._hook_proc)

    def start(self) -> None:
        """Install the hook. Raises MouseHookError on failure."""
        if self._thread is not None:
            return
        self._ready.clear()
        self._start_error = None
        self._thread = threading.Thread(target=self._run, name="mouse-hook", daemon=True)
        self._thread.start()
        if not self._ready.wait(config.MOUSE_HOOK_THREAD_TIMEOUT_SECONDS):
            self.stop()
            raise MouseHookError("The mouse listener did not start in time.")
        if self._start_error:
            self._thread = None
            raise MouseHookError(self._start_error)

    def stop(self) -> None:
        """Remove the hook. Safe to call more than once and from any thread."""
        thread, thread_id = self._thread, self._thread_id
        self._thread = None
        if thread is None or thread_id is None:
            return
        api.user32.PostThreadMessageW(thread_id, api.WM_QUIT, 0, 0)
        if thread is not threading.current_thread():
            thread.join(config.MOUSE_HOOK_THREAD_TIMEOUT_SECONDS)

    def _run(self) -> None:
        self._thread_id = api.kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        # Create this thread's message queue now, so stop() can always post WM_QUIT.
        api.user32.PeekMessageW(ctypes.byref(msg), None, api.WM_USER, api.WM_USER, api.PM_NOREMOVE)

        hook = api.user32.SetWindowsHookExW(api.WH_MOUSE_LL, self._proc, api.kernel32.GetModuleHandleW(None), 0)
        if not hook:
            self._start_error = f"Could not listen to the mouse: {api.last_error_message()}"
            self._ready.set()
            return
        self._ready.set()
        try:
            while api.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            api.user32.UnhookWindowsHookEx(hook)
            log.debug("Mouse hook removed")

    def _hook_proc(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code == api.HC_ACTION:
            kind = _KINDS_BY_MESSAGE.get(w_param)
            if kind is not None:
                info = api.MSLLHOOKSTRUCT.from_address(l_param)
                try:
                    if self._handler(MouseEvent(kind, Point(info.pt.x, info.pt.y))):
                        return _SWALLOW
                except Exception:  # a crash here must never break the user's mouse
                    log.exception("Mouse handler failed")
        return api.user32.CallNextHookEx(None, n_code, w_param, l_param)
