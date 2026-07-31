"""Windows startup registration and single-instance guard (HKCU, no admin)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import ctypes
import winreg

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "R11UltraBattery"
MUTEX_NAME = "Local\\R11UltraBattery_SingleInstance"
ERROR_ALREADY_EXISTS = 183
_ALLOWED_SCRIPTS = frozenset({"main.pyw", "main.py"})

_mutex_handle = None


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def launch_command() -> str:
    """Build a quoted Run-key command limited to this install's entry script."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        if not exe.is_file():
            raise OSError("frozen executable missing")
        return f'"{exe}"'

    root = project_root().resolve()
    script = None
    for name in ("main.pyw", "main.py"):
        candidate = (root / name).resolve()
        if candidate.is_file() and candidate.parent == root and candidate.name in _ALLOWED_SCRIPTS:
            script = candidate
            break
    if script is None:
        raise OSError("startup entry script not found under project root")

    python = Path(sys.executable).resolve()
    pythonw = python.with_name("pythonw.exe")
    launcher = pythonw if pythonw.is_file() else python
    if not launcher.is_file():
        raise OSError("python launcher not found")
    return f'"{launcher}" "{script}"'


def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
            return True
    except OSError:
        return False


def set_startup(enabled: bool) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except OSError as exc:
        log.warning("Failed to update startup: %s", exc)
        return False


def acquire_single_instance() -> bool:
    """Return False if another instance is already running."""
    global _mutex_handle
    try:
        _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not _mutex_handle:
            return True
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            ctypes.windll.kernel32.CloseHandle(_mutex_handle)
            _mutex_handle = None
            return False
        return True
    except OSError:
        return True


def log_file_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "R11UltraBattery"
    base.mkdir(parents=True, exist_ok=True)
    return base / "tray.log"
