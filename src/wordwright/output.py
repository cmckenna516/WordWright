from __future__ import annotations

import ctypes
import logging
import os
import time
from ctypes import wintypes
from enum import Enum
from typing import Callable

LOGGER = logging.getLogger(__name__)


class DeliveryResult(str, Enum):
    """How the transcript reached the user."""

    TYPED = "typed"
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


_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
# Ctrl, Alt, Shift, left Windows, right Windows.
_MODIFIER_KEYS = (0x11, 0x12, 0x10, 0x5B, 0x5C)


class _KeyboardInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _InputUnion(ctypes.Union):
    # The mouse member is the largest; SendInput rejects the whole batch if
    # sizeof(INPUT) does not match what Windows expects.
    _fields_ = [("mi", _MouseInput), ("ki", _KeyboardInput), ("hi", _HardwareInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _InputUnion)]


def prepare_for_typing(text: str) -> str:
    """Collapse line breaks and tabs so typing can never press Enter or Tab."""

    return " ".join(text.split())


def utf16_units(text: str) -> list[int]:
    """UTF-16 code units, which is what Windows Unicode key events carry."""

    data = text.encode("utf-16-le")
    return [int.from_bytes(data[index : index + 2], "little") for index in range(0, len(data), 2)]


def chunk_units(units: list[int], size: int) -> list[list[int]]:
    """Split code units into batches without separating a surrogate pair."""

    chunks: list[list[int]] = []
    start = 0
    while start < len(units):
        end = min(start + size, len(units))
        if end < len(units) and 0xD800 <= units[end - 1] <= 0xDBFF:
            end += 1
        chunks.append(units[start:end])
        start = end
    return chunks


def send_unicode_text(
    text: str,
    chunk_size: int = 64,
    pause_seconds: float = 0.01,
    sleep_function: Callable[[float], None] = time.sleep,
) -> None:
    """Type text into the focused window with Unicode key events.

    The clipboard is never touched. Each batch is checked so a blocked
    destination (for example an app running as administrator) raises instead
    of silently losing the transcript.
    """

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    send_input = user32.SendInput
    send_input.argtypes = [wintypes.UINT, ctypes.POINTER(_Input), ctypes.c_int]
    send_input.restype = wintypes.UINT

    for chunk in chunk_units(utf16_units(text), chunk_size):
        events = (_Input * (len(chunk) * 2))()
        for index, unit in enumerate(chunk):
            for offset, flags in enumerate(
                (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP)
            ):
                event = events[index * 2 + offset]
                event.type = _INPUT_KEYBOARD
                event.union.ki = _KeyboardInput(0, unit, flags, 0, 0)
        sent = send_input(len(events), events, ctypes.sizeof(_Input))
        if sent != len(events):
            raise OSError(
                ctypes.get_last_error(),
                "Windows blocked simulated typing. The destination app may be "
                "running as administrator.",
            )
        # A short pause lets slower apps drain their input queue between batches.
        sleep_function(pause_seconds)


def modifiers_held() -> bool:
    if os.name != "nt":
        return False
    get_key_state = ctypes.windll.user32.GetAsyncKeyState
    return any(get_key_state(key) & 0x8000 for key in _MODIFIER_KEYS)


def _default_type_function() -> Callable[[str], None]:
    if os.name == "nt":
        return send_unicode_text
    from pynput.keyboard import Controller

    return Controller().type


def _default_copy_function(text: str) -> None:
    import pyperclip

    pyperclip.copy(text)


class TextInserter:
    """Type a transcript at the cursor without using the clipboard.

    The clipboard is used only when no text field has focus or Windows blocks
    typing, so a dictation is never lost.
    """

    def __init__(
        self,
        typing_delay_seconds: float = 0.15,
        type_function: Callable[[str], None] | None = None,
        copy_function: Callable[[str], None] = _default_copy_function,
        sleep_function: Callable[[float], None] = time.sleep,
        text_target_detector: Callable[[], bool] = has_active_text_target,
        modifier_detector: Callable[[], bool] = modifiers_held,
        modifier_wait_seconds: float = 2.0,
        clipboard_attempts: int = 5,
        clipboard_retry_seconds: float = 0.05,
    ) -> None:
        self._type = type_function or _default_type_function()
        self._copy = copy_function
        self._delay = typing_delay_seconds
        self._sleep = sleep_function
        self._text_target_detector = text_target_detector
        self._modifiers_held = modifier_detector
        self._modifier_wait_seconds = modifier_wait_seconds
        self._clipboard_attempts = max(1, clipboard_attempts)
        self._clipboard_retry_seconds = clipboard_retry_seconds

    def deliver(self, text: str) -> DeliveryResult:
        text = prepare_for_typing(text)
        if not text:
            raise ValueError("Cannot deliver an empty transcript.")
        if not self._text_target_detector():
            self._copy_to_clipboard(text)
            return DeliveryResult.CLIPBOARD

        self._wait_for_modifier_release()
        self._sleep(self._delay)
        try:
            self._type(text)
        except Exception:
            LOGGER.exception("Typing was blocked; copying the transcript instead")
            self._copy_to_clipboard(text)
            return DeliveryResult.CLIPBOARD
        return DeliveryResult.TYPED

    def _wait_for_modifier_release(self) -> None:
        # Unicode key events sent while Ctrl or Alt is still down are read as
        # shortcuts (Ctrl+S, Alt+F...), so wait for the hotkey to be released.
        step = 0.02
        waited = 0.0
        while self._modifiers_held() and waited < self._modifier_wait_seconds:
            self._sleep(step)
            waited += step

    def _copy_to_clipboard(self, text: str) -> None:
        last_error: Exception | None = None
        for attempt in range(self._clipboard_attempts):
            try:
                self._copy(text)
                return
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self._clipboard_attempts:
                    self._sleep(self._clipboard_retry_seconds)
        raise RuntimeError("Windows clipboard remained unavailable.") from last_error
