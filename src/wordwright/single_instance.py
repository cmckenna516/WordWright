from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any


MUTEX_NAME = "Local\\WordwrightDesktopApp-C282C902-2D52-49F5-BC43-26EE01E57867"
SHOW_EVENT_NAME = "Local\\WordwrightShowLauncher-C282C902-2D52-49F5-BC43-26EE01E57867"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0


@dataclass(slots=True)
class SingleInstance:
    """Hold a Windows named mutex for the lifetime of the application."""

    handle: int | None = None
    show_event_handle: int | None = None
    kernel32: Any | None = None

    @classmethod
    def acquire(cls) -> SingleInstance | None:
        if os.name != "nt":
            return cls()

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        wait_for_single_object = kernel32.WaitForSingleObject
        wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        wait_for_single_object.restype = wintypes.DWORD
        create_event = kernel32.CreateEventW
        create_event.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        create_event.restype = wintypes.HANDLE
        show_event = create_event(None, False, False, SHOW_EVENT_NAME)
        if not show_event:
            raise ctypes.WinError(ctypes.get_last_error())

        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        create_mutex.restype = wintypes.HANDLE
        handle = create_mutex(None, False, MUTEX_NAME)
        if not handle:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(show_event)
            raise ctypes.WinError(error)
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            kernel32.CloseHandle(show_event)
            return None
        return cls(
            handle=int(handle),
            show_event_handle=int(show_event),
            kernel32=kernel32,
        )

    @classmethod
    def request_show(cls) -> bool:
        """Ask the existing process to reveal its launcher window."""

        if os.name != "nt":
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        set_event = kernel32.SetEvent
        set_event.argtypes = [wintypes.HANDLE]
        set_event.restype = wintypes.BOOL
        open_event = kernel32.OpenEventW
        open_event.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        open_event.restype = wintypes.HANDLE
        handle = open_event(EVENT_MODIFY_STATE, False, SHOW_EVENT_NAME)
        if not handle:
            return False
        try:
            return bool(set_event(handle))
        finally:
            close_handle(handle)

    def consume_show_request(self) -> bool:
        """Consume one pending launcher request without blocking."""

        if self.show_event_handle is None or self.kernel32 is None:
            return False
        return self.kernel32.WaitForSingleObject(self.show_event_handle, 0) == WAIT_OBJECT_0

    def release(self) -> None:
        if self.kernel32 is None:
            return
        if self.handle is not None:
            self.kernel32.CloseHandle(self.handle)
        if self.show_event_handle is not None:
            self.kernel32.CloseHandle(self.show_event_handle)
        self.handle = None
        self.show_event_handle = None


def show_already_running_message() -> None:
    if os.name != "nt":
        return
    ctypes.windll.user32.MessageBoxW(
        None,
        "Wordwright is already running. Open it from the system tray near the clock.",
        "Wordwright",
        0x00000040,
    )
