from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from enum import Enum
from typing import Any, Callable


class DeliveryResult(str, Enum):
    """How the transcript reached the user."""

    PASTED = "pasted"
    CLIPBOARD = "clipboard"


class _Rect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _GuiThreadInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", _Rect),
    ]


def has_active_text_target() -> bool:
    """Best-effort check for a focused Windows text insertion target.

    A visible caret or native edit class is conclusive. Modern browsers and
    Electron applications often expose only a generic focused rendering host,
    so an unknown focused control in another application is treated as a valid
    destination. Shell surfaces and Wordwright's own windows remain excluded.
    """

    if os.name != "nt":
        return True
    try:
        user32 = ctypes.windll.user32
        get_foreground = user32.GetForegroundWindow
        get_foreground.restype = wintypes.HWND
        get_window_thread = user32.GetWindowThreadProcessId
        get_window_thread.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        get_window_thread.restype = wintypes.DWORD
        get_gui_thread_info = user32.GetGUIThreadInfo
        get_gui_thread_info.argtypes = [wintypes.DWORD, ctypes.POINTER(_GuiThreadInfo)]
        get_gui_thread_info.restype = wintypes.BOOL
        get_class_name = user32.GetClassNameW
        get_class_name.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        get_class_name.restype = ctypes.c_int

        foreground = get_foreground()
        if not foreground:
            return False
        process_id = wintypes.DWORD()
        thread_id = get_window_thread(foreground, ctypes.byref(process_id))
        info = _GuiThreadInfo()
        info.cbSize = ctypes.sizeof(_GuiThreadInfo)
        if not get_gui_thread_info(thread_id, ctypes.byref(info)):
            return False
        focused = info.hwndFocus or info.hwndCaret

        def window_class(handle: int | None) -> str:
            if not handle:
                return ""
            class_name = ctypes.create_unicode_buffer(256)
            get_class_name(handle, class_name, len(class_name))
            return class_name.value

        foreground_class = window_class(foreground)
        focused_class = window_class(focused)
        caret_visible = info.rcCaret.bottom > info.rcCaret.top
        current_process = ctypes.windll.kernel32.GetCurrentProcessId()
        return _is_probable_text_target(
            foreground_class=foreground_class,
            focused_class=focused_class,
            caret_visible=caret_visible,
            owns_foreground=process_id.value == current_process,
        )
    except (AttributeError, OSError, TypeError):
        return False


def _is_probable_text_target(
    foreground_class: str,
    focused_class: str,
    caret_visible: bool,
    owns_foreground: bool,
) -> bool:
    """Classify a focused control without blocking modern text surfaces."""

    if owns_foreground:
        return False
    foreground = foreground_class.casefold()
    focused = focused_class.casefold()
    shell_classes = {
        "progman",
        "workerw",
        "shell_traywnd",
        "shelldll_defview",
        "syslistview32",
    }
    non_text_controls = {
        "button",
        "static",
        "toolbarwindow32",
        "systabcontrol32",
        "sysheader32",
    }
    if foreground in shell_classes or focused in shell_classes | non_text_controls:
        return False
    if caret_visible:
        return True
    native_edit = any(
        marker in focused
        for marker in ("edit", "richedit", "scintilla", "consolewindowclass")
    )
    if native_edit:
        return True
    if focused:
        # Chromium, Firefox, Electron, Office, Qt, and many custom controls use
        # a generic focused host even while an editable child owns the caret.
        return True
    modern_hosts = (
        "chrome_widgetwin",
        "chrome_renderwidgethosthwnd",
        "mozillawindowclass",
        "applicationframewindow",
        "windows.ui.core.corewindow",
        "hwndwrapper",
        "qt",
    )
    return any(marker in foreground for marker in modern_hosts)


class TextInserter:
    """Leave a transcript on the clipboard and issue a paste command."""

    def __init__(
        self,
        paste_delay_seconds: float = 0.15,
        copy_function: Callable[[str], None] | None = None,
        keyboard_controller: Any | None = None,
        ctrl_key: Any | None = None,
        sleep_function: Callable[[float], None] = time.sleep,
        text_target_detector: Callable[[], bool] = has_active_text_target,
        clipboard_attempts: int = 5,
        clipboard_retry_seconds: float = 0.05,
    ) -> None:
        if copy_function is None:
            import pyperclip

            copy_function = pyperclip.copy
        if keyboard_controller is None or ctrl_key is None:
            from pynput.keyboard import Controller, Key

            keyboard_controller = keyboard_controller or Controller()
            ctrl_key = ctrl_key or Key.ctrl

        self._copy = copy_function
        self._keyboard = keyboard_controller
        self._ctrl = ctrl_key
        self._delay = paste_delay_seconds
        self._sleep = sleep_function
        self._text_target_detector = text_target_detector
        self._clipboard_attempts = max(1, clipboard_attempts)
        self._clipboard_retry_seconds = clipboard_retry_seconds

    def deliver(self, text: str) -> DeliveryResult:
        if not text:
            raise ValueError("Cannot deliver an empty transcript.")

        last_error: Exception | None = None
        for attempt in range(self._clipboard_attempts):
            try:
                self._copy(text)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self._clipboard_attempts:
                    self._sleep(self._clipboard_retry_seconds)
        if last_error is not None:
            raise RuntimeError("Windows clipboard remained unavailable.") from last_error
        if not self._text_target_detector():
            return DeliveryResult.CLIPBOARD
        self._sleep(self._delay)
        self._keyboard.press(self._ctrl)
        try:
            self._keyboard.press("v")
            self._keyboard.release("v")
        finally:
            self._keyboard.release(self._ctrl)
        return DeliveryResult.PASTED
