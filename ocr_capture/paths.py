"""Where the app keeps its files.

Everything (settings, log, captures) lives in one folder so the app is
portable: copy the exe and ``settings.json`` to another PC and it just works.
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import config


def app_dir() -> Path:
    """Folder of the running exe, or the project root when run from source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def settings_path() -> Path:
    return app_dir() / config.SETTINGS_FILE_NAME


def log_path() -> Path:
    return app_dir() / config.LOG_FILE_NAME


def resolve_user_path(path_text: str) -> Path:
    """Turn a path from settings.json into an absolute path.

    Relative paths are relative to the app folder (not the current working
    directory), so a shortcut started from anywhere behaves the same.
    """
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else app_dir() / path
