from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any


MUTEX_NAME = "Local\\WordwrightDesktopApp-C282C902-2D52-49F5-BC43-26EE01E57867"
ERROR_ALREADY_EXISTS = 183


@dataclass(slots=True)
class SingleInstance:
    """Hold a Windows named mutex for the lifetime of the application."""

    handle: int | None = None
    kernel32: Any | None = None

    @classmethod
    def acquire(cls) -> SingleInstance | None:
        if os.name != "nt":
            return cls()

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        create_mutex.restype = wintypes.HANDLE
        handle = create_mutex(None, False, MUTEX_NAME)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return None
        return cls(handle=int(handle), kernel32=kernel32)

    def release(self) -> None:
        if self.handle is None or self.kernel32 is None:
            return
        self.kernel32.CloseHandle(self.handle)
        self.handle = None


def show_already_running_message() -> None:
    if os.name != "nt":
        return
    ctypes.windll.user32.MessageBoxW(
        None,
        "Wordwright is already running. Open it from the system tray near the clock.",
        "Wordwright",
        0x00000040,
    )
