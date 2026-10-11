"""Global shortcuts: the dictation toggle and Esc-to-cancel.

On Windows the shortcut is registered with the operating system
(``RegisterHotKey``). Windows then fires it only when exactly that
combination is pressed, so a stray Space or Ctrl can never start a
recording, and the shortcut is not also typed into the focused app. Esc is
registered only while recording, so it works normally the rest of the time.

The pynput listener this replaces tracked key state itself. If it missed a
Ctrl or Alt release (after a lock screen, a focus change, or injected input),
it believed the modifiers were still held and fired on Space alone.
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)

DEFAULT_HOTKEY = "ctrl+alt+space"

MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")
MODIFIER_CHOICES: dict[str, tuple[str, ...]] = {
    "Ctrl + Alt": ("ctrl", "alt"),
    "Ctrl + Shift": ("ctrl", "shift"),
    "Alt + Shift": ("alt", "shift"),
    "Ctrl + Alt + Shift": ("ctrl", "alt", "shift"),
    "Win + Alt": ("win", "alt"),
}
KEY_CHOICES: tuple[str, ...] = (
    ("space",)
    + tuple(chr(code) for code in range(ord("a"), ord("z") + 1))
    + tuple(str(digit) for digit in range(10))
    + tuple(f"f{number}" for number in range(1, 13))
)

_MOD_FLAGS = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}
_MOD_NOREPEAT = 0x4000
_VK_ESCAPE = 0x1B
_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_WM_APP = 0x8000
_MSG_SET_CANCEL = _WM_APP + 1
_MSG_SET_TOGGLE = _WM_APP + 2
_TOGGLE_ID = 1
_CANCEL_ID = 2
_ERROR_HOTKEY_ALREADY_REGISTERED = 1409


@dataclass(frozen=True, slots=True)
class Hotkey:
    modifiers: tuple[str, ...]
    key: str

    @property
    def spec(self) -> str:
        return "+".join((*self.modifiers, self.key))

    @property
    def label(self) -> str:
        """Human-readable form, for example ``Ctrl+Alt+Space``."""

        names = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}
        key = self.key.upper() if len(self.key) == 1 or self.key.startswith("f") else self.key.title()
        return "+".join([*(names[m] for m in self.modifiers), key])

    @property
    def parts(self) -> list[str]:
        return self.label.split("+")

    @property
    def virtual_key(self) -> int:
        if self.key == "space":
            return 0x20
        if self.key.startswith("f") and self.key[1:].isdigit():
            return 0x70 + int(self.key[1:]) - 1
        return ord(self.key.upper())

    @property
    def windows_modifiers(self) -> int:
        flags = _MOD_NOREPEAT
        for modifier in self.modifiers:
            flags |= _MOD_FLAGS[modifier]
        return flags

    @property
    def pynput_spec(self) -> str:
        key = self.key if len(self.key) == 1 else f"<{self.key}>"
        mods = ["<cmd>" if m == "win" else f"<{m}>" for m in self.modifiers]
        return "+".join([*mods, key])


def parse_hotkey(spec: str) -> Hotkey:
    """Parse ``ctrl+alt+space``-style text and reject unsafe shortcuts."""

    parts = [part.strip().lower() for part in str(spec).split("+") if part.strip()]
    modifiers = [part for part in parts if part in _MOD_FLAGS]
    keys = [part for part in parts if part not in _MOD_FLAGS]
    if len(keys) != 1:
        raise ValueError("A shortcut needs exactly one main key, such as Space or K.")
    key = keys[0]
    if key not in KEY_CHOICES:
        raise ValueError(f"'{key}' can't be used as the shortcut key.")
    if len(set(modifiers)) != len(modifiers):
        raise ValueError("A modifier key is listed twice.")
    if not {"ctrl", "alt", "win"} & set(modifiers):
        # Shift alone would fire while typing capital letters or symbols.
        raise ValueError("A shortcut needs Ctrl, Alt, or Win so it can't fire while typing.")
    ordered = tuple(m for m in MODIFIER_ORDER if m in modifiers)
    return Hotkey(ordered, key)


def hotkey_label(spec: str) -> str:
    try:
        return parse_hotkey(spec).label
    except ValueError:
        return parse_hotkey(DEFAULT_HOTKEY).label


class HotkeyError(RuntimeError):
    pass


def _registration_error(hotkey: Hotkey, code: int) -> str:
    if code == _ERROR_HOTKEY_ALREADY_REGISTERED:
        return (
            f"{hotkey.label} is already used by another app or by Windows. "
            "Choose a different shortcut in Settings."
        )
    return f"{hotkey.label} could not be registered (Windows error {code})."


class WindowsHotkeys:
    """System hotkeys on a dedicated thread with its own message loop."""

    def __init__(
        self,
        spec: str,
        on_toggle: Callable[[], None],
        on_cancel: Callable[[], None],
        user32: Any | None = None,
        kernel32: Any | None = None,
        get_last_error: Callable[[], int] | None = None,
    ) -> None:
        self._hotkey = parse_hotkey(spec)
        self._get_last_error = get_last_error or (lambda: ctypes.get_last_error())
        self._on_toggle = on_toggle
        self._on_cancel = on_cancel
        self._user32 = user32
        self._kernel32 = kernel32
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._changed = threading.Event()
        self._pending: Hotkey | None = None
        self._change_error: str | None = None
        self.registration_error: str | None = None

    @property
    def label(self) -> str:
        return self._hotkey.label

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="wordwright-hotkeys", daemon=True)
        self._thread.start()
        if not self._ready.wait(5.0):
            self.registration_error = "The shortcut listener did not start."

    def wait_until_ready(self) -> None:
        self._ready.wait(5.0)
        if self.registration_error:
            raise HotkeyError(self.registration_error)

    def set_cancel_enabled(self, enabled: bool) -> None:
        self._post(_MSG_SET_CANCEL, 1 if enabled else 0)

    def set_hotkey(self, spec: str) -> str | None:
        """Switch to a new shortcut. Returns an error message, or None on success."""

        try:
            hotkey = parse_hotkey(spec)
        except ValueError as exc:
            return str(exc)
        if hotkey == self._hotkey and not self.registration_error:
            return None
        self._pending = hotkey
        self._change_error = None
        self._changed.clear()
        if not self._post(_MSG_SET_TOGGLE, 0):
            return "The shortcut listener is not running."
        if not self._changed.wait(3.0):
            return "Windows did not respond while changing the shortcut."
        return self._change_error

    def stop(self) -> None:
        self._post(_WM_QUIT, 0)

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _post(self, message: int, wparam: int) -> bool:
        if not self._thread_id:
            return False
        return bool(self._api()[0].PostThreadMessageW(self._thread_id, message, wparam, 0))

    def _api(self) -> tuple[Any, Any]:
        if self._user32 is None:
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            self._user32.RegisterHotKey.restype = wintypes.BOOL
            self._user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self._user32.UnregisterHotKey.restype = wintypes.BOOL
            self._user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            self._user32.GetMessageW.restype = wintypes.BOOL
            self._user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
            self._user32.PeekMessageW.restype = wintypes.BOOL
            self._user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            self._user32.PostThreadMessageW.restype = wintypes.BOOL
        if self._kernel32 is None:
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        return self._user32, self._kernel32

    def _register(self, identifier: int, modifiers: int, virtual_key: int) -> int:
        """Register a hotkey on this thread. Returns 0 or a Windows error code."""

        user32, _ = self._api()
        if user32.RegisterHotKey(None, identifier, modifiers, virtual_key):
            return 0
        return self._get_last_error() or 1

    def _run(self) -> None:
        message = wintypes.MSG()
        try:
            user32, kernel32 = self._api()
            # Create this thread's message queue before anyone posts to it.
            user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            self._thread_id = kernel32.GetCurrentThreadId()
            code = self._register(
                _TOGGLE_ID, self._hotkey.windows_modifiers, self._hotkey.virtual_key
            )
            if code:
                self.registration_error = _registration_error(self._hotkey, code)
                LOGGER.warning(self.registration_error)
            else:
                LOGGER.info("Shortcut registered: %s", self._hotkey.label)
        except Exception:
            LOGGER.exception("The shortcut listener could not start")
            self.registration_error = "The keyboard shortcut could not be set up."
            return
        finally:
            self._ready.set()

        cancel_registered = False
        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == _WM_HOTKEY:
                    self._dispatch(message.wParam)
                elif message.message == _MSG_SET_CANCEL:
                    want = bool(message.wParam)
                    if want and not cancel_registered:
                        # Ignore failure: Esc is a convenience, not essential.
                        cancel_registered = self._register(_CANCEL_ID, _MOD_NOREPEAT, _VK_ESCAPE) == 0
                    elif not want and cancel_registered:
                        user32.UnregisterHotKey(None, _CANCEL_ID)
                        cancel_registered = False
                elif message.message == _MSG_SET_TOGGLE:
                    self._apply_pending()
        finally:
            user32.UnregisterHotKey(None, _TOGGLE_ID)
            if cancel_registered:
                user32.UnregisterHotKey(None, _CANCEL_ID)

    def _apply_pending(self) -> None:
        user32, _ = self._api()
        new = self._pending
        if new is None:
            self._changed.set()
            return
        had_old = self.registration_error is None
        if had_old:
            user32.UnregisterHotKey(None, _TOGGLE_ID)
        code = self._register(_TOGGLE_ID, new.windows_modifiers, new.virtual_key)
        if code:
            self._change_error = _registration_error(new, code)
            if had_old:
                # Put the previous shortcut back so dictation keeps working.
                self._register(_TOGGLE_ID, self._hotkey.windows_modifiers, self._hotkey.virtual_key)
        else:
            LOGGER.info("Shortcut changed: %s", new.label)
            self._hotkey = new
            self.registration_error = None
        self._changed.set()

    def _dispatch(self, identifier: int) -> None:
        if identifier == _TOGGLE_ID:
            callback = self._on_toggle
        elif identifier == _CANCEL_ID:
            callback = self._on_cancel
        else:
            return
        try:
            callback()
        except Exception:
            LOGGER.exception("Shortcut handler failed")


class PynputHotkeys:
    """Development fallback for non-Windows systems."""

    def __init__(
        self,
        spec: str,
        on_toggle: Callable[[], None],
        on_cancel: Callable[[], None],
        listener_factory: Callable[..., Any] | None = None,
    ) -> None:
        if listener_factory is None:
            from pynput.keyboard import GlobalHotKeys

            listener_factory = GlobalHotKeys
        self._factory = listener_factory
        self._on_toggle = on_toggle
        self._on_cancel = on_cancel
        self._hotkey = parse_hotkey(spec)
        self._listener = self._make_listener()
        self.registration_error: str | None = None

    @property
    def label(self) -> str:
        return self._hotkey.label

    def _make_listener(self) -> Any:
        return self._factory({self._hotkey.pynput_spec: self._on_toggle, "<esc>": self._on_cancel})

    def start(self) -> None:
        self._listener.start()

    def wait_until_ready(self) -> None:
        self._listener.wait()

    def set_cancel_enabled(self, enabled: bool) -> None:
        del enabled

    def set_hotkey(self, spec: str) -> str | None:
        try:
            self._hotkey = parse_hotkey(spec)
        except ValueError as exc:
            return str(exc)
        self._listener.stop()
        self._listener = self._make_listener()
        self._listener.start()
        return None

    def stop(self) -> None:
        self._listener.stop()

    def join(self, timeout: float | None = None) -> None:
        self._listener.join(timeout)


def create_hotkeys(
    spec: str,
    on_toggle: Callable[[], None],
    on_cancel: Callable[[], None],
) -> WindowsHotkeys | PynputHotkeys:
    if os.name == "nt":
        return WindowsHotkeys(spec, on_toggle, on_cancel)
    return PynputHotkeys(spec, on_toggle, on_cancel)
