"""Global shortcuts for toggle and press-and-hold dictation.

Windows' ``RegisterHotKey`` API remains the reliable path for the toggle
shortcut and Esc-to-cancel. Press-and-hold needs key-up events as well as
key-down events, so a small pynput listener tracks that one chord. A Windows
key-state watchdog also ends a hold if a release event is lost during a lock
screen or focus transition.
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

DEFAULT_TOGGLE_HOTKEY = "ctrl+shift+space"
DEFAULT_HOLD_HOTKEY = "ctrl+alt"
# Kept as an alias for callers from earlier releases.
DEFAULT_HOTKEY = DEFAULT_TOGGLE_HOTKEY

MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")
MODIFIER_CHOICES: dict[str, tuple[str, ...]] = {
    "Ctrl + Alt": ("ctrl", "alt"),
    "Ctrl + Shift": ("ctrl", "shift"),
    "Alt + Shift": ("alt", "shift"),
    "Ctrl + Alt + Shift": ("ctrl", "alt", "shift"),
    "Alt + Win": ("alt", "win"),
}
KEY_CHOICES: tuple[str, ...] = (
    ("space",)
    + tuple(chr(code) for code in range(ord("a"), ord("z") + 1))
    + tuple(str(digit) for digit in range(10))
    + tuple(f"f{number}" for number in range(1, 13))
)

_MOD_FLAGS = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}
_MOD_NOREPEAT = 0x4000
_MODIFIER_VKS: dict[str, tuple[int, ...]] = {
    "ctrl": (0x11,),
    "alt": (0x12,),
    "shift": (0x10,),
    "win": (0x5B, 0x5C),
}
_VK_ESCAPE = 0x1B
_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_WM_APP = 0x8000
_MSG_SET_CANCEL = _WM_APP + 1
_MSG_SET_TOGGLE = _WM_APP + 2
_TOGGLE_ID = 1
_CANCEL_ID = 2
_ERROR_HOTKEY_ALREADY_REGISTERED = 1409


def _key_label(key: str) -> str:
    return key.upper() if len(key) == 1 or key.startswith("f") else key.title()


def _modifier_label(modifier: str) -> str:
    return {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}[modifier]


@dataclass(frozen=True, slots=True)
class Hotkey:
    modifiers: tuple[str, ...]
    key: str

    @property
    def spec(self) -> str:
        return "+".join((*self.modifiers, self.key))

    @property
    def label(self) -> str:
        return "+".join([*(_modifier_label(m) for m in self.modifiers), _key_label(self.key)])

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


@dataclass(frozen=True, slots=True)
class HoldHotkey:
    modifiers: tuple[str, ...]
    key: str | None = None

    @property
    def spec(self) -> str:
        return "+".join((*self.modifiers, *((self.key,) if self.key else ())))

    @property
    def label(self) -> str:
        parts = [*(_modifier_label(m) for m in self.modifiers)]
        if self.key:
            parts.append(_key_label(self.key))
        return "+".join(parts)

    @property
    def required_names(self) -> set[str]:
        names = set(self.modifiers)
        if self.key:
            names.add(self.key)
        return names

    @property
    def virtual_keys(self) -> tuple[tuple[int, ...], ...]:
        keys = [_MODIFIER_VKS[modifier] for modifier in self.modifiers]
        if self.key:
            keys.append((Hotkey((), self.key).virtual_key,))
        return tuple(keys)


def _parse_parts(spec: str) -> tuple[list[str], list[str]]:
    parts = [part.strip().lower() for part in str(spec).split("+") if part.strip()]
    modifiers = [part for part in parts if part in _MOD_FLAGS]
    keys = [part for part in parts if part not in _MOD_FLAGS]
    if len(set(modifiers)) != len(modifiers):
        raise ValueError("A modifier key is listed twice.")
    return modifiers, keys


def parse_hotkey(spec: str) -> Hotkey:
    """Parse a toggle shortcut and require exactly one non-modifier key."""

    modifiers, keys = _parse_parts(spec)
    if len(keys) != 1:
        raise ValueError("A shortcut needs exactly one main key, such as Space or K.")
    key = keys[0]
    if key not in KEY_CHOICES:
        raise ValueError(f"'{key}' can't be used as the shortcut key.")
    if not {"ctrl", "alt", "win"} & set(modifiers):
        raise ValueError("A shortcut needs Ctrl, Alt, or Win so it can't fire while typing.")
    ordered = tuple(m for m in MODIFIER_ORDER if m in modifiers)
    return Hotkey(ordered, key)


def parse_hold_hotkey(spec: str) -> HoldHotkey:
    """Parse a hold chord, allowing modifiers alone (for example Ctrl+Alt)."""

    modifiers, keys = _parse_parts(spec)
    if len(keys) > 1:
        raise ValueError("A hold shortcut can use at most one main key.")
    if keys and keys[0] not in KEY_CHOICES:
        raise ValueError(f"'{keys[0]}' can't be used as the hold key.")
    if len(modifiers) < 2:
        raise ValueError("A hold shortcut needs at least two modifier keys.")
    if not {"ctrl", "alt", "win"} & set(modifiers):
        raise ValueError("A hold shortcut needs Ctrl, Alt, or Win.")
    ordered = tuple(m for m in MODIFIER_ORDER if m in modifiers)
    return HoldHotkey(ordered, keys[0] if keys else None)


def hotkey_label(spec: str) -> str:
    try:
        return parse_hotkey(spec).label
    except ValueError:
        return parse_hotkey(DEFAULT_TOGGLE_HOTKEY).label


def hold_hotkey_label(spec: str) -> str:
    try:
        return parse_hold_hotkey(spec).label
    except ValueError:
        return parse_hold_hotkey(DEFAULT_HOLD_HOTKEY).label


def shortcut_conflict(toggle: Hotkey, hold: HoldHotkey) -> str | None:
    """Return a message when pressing the toggle would also activate hold mode."""

    toggle_names = {*toggle.modifiers, toggle.key}
    if hold.required_names <= toggle_names:
        return (
            f"{hold.label} overlaps {toggle.label}. Choose shortcuts that do not share "
            "the complete hold combination."
        )
    return None


class HotkeyError(RuntimeError):
    pass


def _registration_error(hotkey: Hotkey, code: int) -> str:
    if code == _ERROR_HOTKEY_ALREADY_REGISTERED:
        return (
            f"{hotkey.label} is already used by another app or by Windows. "
            "Choose a different shortcut in Settings."
        )
    return f"{hotkey.label} could not be registered (Windows error {code})."


class HoldKeyListener:
    """Track a hold chord and emit exactly one start and one stop per hold."""

    _ALIASES = {
        "ctrl": "ctrl", "ctrl_l": "ctrl", "ctrl_r": "ctrl",
        # AltGr is intentionally excluded. On Windows it is commonly reported
        # together with a synthetic Ctrl press, so treating it as ordinary Alt
        # would make the default Ctrl+Alt hold chord fire while typing symbols
        # on many international keyboard layouts.
        "alt": "alt", "alt_l": "alt", "alt_r": "alt",
        "shift": "shift", "shift_l": "shift", "shift_r": "shift",
        "cmd": "win", "cmd_l": "win", "cmd_r": "win", "win": "win",
        "space": "space",
    }

    def __init__(
        self,
        spec: str,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        listener_factory: Callable[..., Any] | None = None,
        key_state: Callable[[int], bool] | None = None,
    ) -> None:
        self._hotkey = parse_hold_hotkey(spec)
        self._on_start = on_start
        self._on_stop = on_stop
        self._listener_factory = listener_factory or self._default_listener_factory
        self._key_state = key_state
        if self._key_state is None and os.name == "nt":
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._key_state = lambda virtual_key: bool(user32.GetAsyncKeyState(virtual_key) & 0x8000)
        self._listener: Any | None = None
        # Keep the physical key identities as well as their logical modifier.
        # Otherwise releasing left Ctrl would clear "ctrl" while right Ctrl is
        # still held, ending an active hold too early.
        self._pressed: dict[str, set[str]] = {}
        self._active = False
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._watchdog: threading.Thread | None = None

    @property
    def label(self) -> str:
        return self._hotkey.label

    @staticmethod
    def _default_listener_factory(**callbacks: Any) -> Any:
        from pynput.keyboard import Listener

        return Listener(**callbacks)

    @classmethod
    def _key_identity(cls, key: Any) -> tuple[str, str] | None:
        if isinstance(key, str):
            raw = key
        else:
            char = getattr(key, "char", None)
            raw = char if char else getattr(key, "name", None) or str(key)
        raw = str(raw).lower().replace("key.", "").strip("<>'\"")
        if raw in cls._ALIASES:
            return cls._ALIASES[raw], raw
        if raw in KEY_CHOICES:
            return raw, raw
        return None

    def start(self) -> None:
        self._stop_event.clear()
        self._listener = self._listener_factory(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()
        if self._key_state is not None:
            self._watchdog = threading.Thread(
                target=self._watch_key_state,
                name="wordwright-hold-watchdog",
                daemon=True,
            )
            self._watchdog.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._listener is not None:
            self._listener.stop()

    def join(self, timeout: float | None = None) -> None:
        if self._listener is not None:
            self._listener.join(timeout)
        if self._watchdog is not None:
            self._watchdog.join(timeout)

    def set_hotkey(self, spec: str) -> str | None:
        try:
            hotkey = parse_hold_hotkey(spec)
        except ValueError as exc:
            return str(exc)
        with self._lock:
            if self._active:
                return "Release the hold shortcut before changing it."
            self._hotkey = hotkey
            self._pressed.clear()
        return None

    def _matches(self) -> bool:
        return self._hotkey.required_names <= self._pressed.keys()

    def _handle_press(self, key: Any) -> None:
        identity = self._key_identity(key)
        if identity is None:
            return
        name, physical = identity
        callback: Callable[[], None] | None = None
        with self._lock:
            self._pressed.setdefault(name, set()).add(physical)
            if not self._active and self._matches():
                self._active = True
                callback = self._on_start
        self._invoke(callback)

    def _handle_release(self, key: Any) -> None:
        identity = self._key_identity(key)
        if identity is None:
            return
        name, physical = identity
        callback: Callable[[], None] | None = None
        with self._lock:
            physical_keys = self._pressed.get(name)
            if physical_keys is not None:
                physical_keys.discard(physical)
                if not physical_keys:
                    self._pressed.pop(name, None)
            if self._active and not self._matches():
                self._active = False
                callback = self._on_stop
        self._invoke(callback)

    def _watch_key_state(self) -> None:
        while not self._stop_event.wait(0.05):
            with self._lock:
                active = self._active
                virtual_keys = self._hotkey.virtual_keys
            if not active or self._key_state is None:
                continue
            if all(any(self._key_state(key) for key in alternatives) for alternatives in virtual_keys):
                continue
            callback: Callable[[], None] | None = None
            with self._lock:
                if self._active:
                    self._active = False
                    self._pressed.clear()
                    callback = self._on_stop
            self._invoke(callback)

    @staticmethod
    def _invoke(callback: Callable[[], None] | None) -> None:
        if callback is None:
            return
        try:
            callback()
        except Exception:
            LOGGER.exception("Hold shortcut handler failed")


class WindowsHotkeys:
    """Windows toggle/cancel registrations plus a key-up-aware hold listener."""

    def __init__(
        self,
        spec: str,
        on_toggle: Callable[[], None],
        on_cancel: Callable[[], None],
        user32: Any | None = None,
        kernel32: Any | None = None,
        get_last_error: Callable[[], int] | None = None,
        hold_spec: str = DEFAULT_HOLD_HOTKEY,
        on_hold_start: Callable[[], None] = lambda: None,
        on_hold_stop: Callable[[], None] = lambda: None,
        hold_listener: HoldKeyListener | None = None,
    ) -> None:
        self._hotkey = parse_hotkey(spec)
        self._hold_hotkey = parse_hold_hotkey(hold_spec)
        conflict = shortcut_conflict(self._hotkey, self._hold_hotkey)
        if conflict:
            raise ValueError(conflict)
        self._get_last_error = get_last_error or (lambda: ctypes.get_last_error())
        self._on_toggle = on_toggle
        self._on_cancel = on_cancel
        self._user32 = user32
        self._kernel32 = kernel32
        self._hold_listener = hold_listener or HoldKeyListener(
            hold_spec, on_hold_start, on_hold_stop
        )
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

    @property
    def hold_label(self) -> str:
        return self._hold_hotkey.label

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="wordwright-hotkeys", daemon=True)
        self._thread.start()
        if not self._ready.wait(5.0):
            self.registration_error = "The shortcut listener did not start."
        try:
            self._hold_listener.start()
        except Exception:
            LOGGER.exception("The hold shortcut listener could not start")
            message = "The hold shortcut could not be set up."
            self.registration_error = f"{self.registration_error} {message}" if self.registration_error else message

    def wait_until_ready(self) -> None:
        self._ready.wait(5.0)
        if self.registration_error:
            raise HotkeyError(self.registration_error)

    def set_cancel_enabled(self, enabled: bool) -> None:
        self._post(_MSG_SET_CANCEL, 1 if enabled else 0)

    def set_hotkey(self, spec: str) -> str | None:
        try:
            hotkey = parse_hotkey(spec)
        except ValueError as exc:
            return str(exc)
        conflict = shortcut_conflict(hotkey, self._hold_hotkey)
        if conflict:
            return conflict
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

    def set_hold_hotkey(self, spec: str) -> str | None:
        try:
            hotkey = parse_hold_hotkey(spec)
        except ValueError as exc:
            return str(exc)
        conflict = shortcut_conflict(self._hotkey, hotkey)
        if conflict:
            return conflict
        error = self._hold_listener.set_hotkey(hotkey.spec)
        if error is None:
            self._hold_hotkey = hotkey
            LOGGER.info("Hold shortcut changed: %s", hotkey.label)
        return error

    def stop(self) -> None:
        self._hold_listener.stop()
        self._post(_WM_QUIT, 0)

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)
        self._hold_listener.join(timeout)

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
        user32, _ = self._api()
        if user32.RegisterHotKey(None, identifier, modifiers, virtual_key):
            return 0
        return self._get_last_error() or 1

    def _run(self) -> None:
        message = wintypes.MSG()
        try:
            user32, kernel32 = self._api()
            user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            self._thread_id = kernel32.GetCurrentThreadId()
            code = self._register(
                _TOGGLE_ID, self._hotkey.windows_modifiers, self._hotkey.virtual_key
            )
            if code:
                self.registration_error = _registration_error(self._hotkey, code)
                LOGGER.warning(self.registration_error)
            else:
                LOGGER.info("Toggle shortcut registered: %s", self._hotkey.label)
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
                self._register(_TOGGLE_ID, self._hotkey.windows_modifiers, self._hotkey.virtual_key)
        else:
            LOGGER.info("Toggle shortcut changed: %s", new.label)
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
        hold_spec: str = DEFAULT_HOLD_HOTKEY,
        on_hold_start: Callable[[], None] = lambda: None,
        on_hold_stop: Callable[[], None] = lambda: None,
        hold_listener: HoldKeyListener | None = None,
    ) -> None:
        if listener_factory is None:
            from pynput.keyboard import GlobalHotKeys

            listener_factory = GlobalHotKeys
        self._factory = listener_factory
        self._on_toggle = on_toggle
        self._on_cancel = on_cancel
        self._hotkey = parse_hotkey(spec)
        self._hold_hotkey = parse_hold_hotkey(hold_spec)
        conflict = shortcut_conflict(self._hotkey, self._hold_hotkey)
        if conflict:
            raise ValueError(conflict)
        self._listener = self._make_listener()
        self._hold_listener = hold_listener or HoldKeyListener(
            hold_spec, on_hold_start, on_hold_stop
        )
        self.registration_error: str | None = None

    @property
    def label(self) -> str:
        return self._hotkey.label

    @property
    def hold_label(self) -> str:
        return self._hold_hotkey.label

    def _make_listener(self) -> Any:
        return self._factory({self._hotkey.pynput_spec: self._on_toggle, "<esc>": self._on_cancel})

    def start(self) -> None:
        self._listener.start()
        self._hold_listener.start()

    def wait_until_ready(self) -> None:
        self._listener.wait()

    def set_cancel_enabled(self, enabled: bool) -> None:
        del enabled

    def set_hotkey(self, spec: str) -> str | None:
        try:
            hotkey = parse_hotkey(spec)
        except ValueError as exc:
            return str(exc)
        conflict = shortcut_conflict(hotkey, self._hold_hotkey)
        if conflict:
            return conflict
        self._hotkey = hotkey
        self._listener.stop()
        self._listener = self._make_listener()
        self._listener.start()
        return None

    def set_hold_hotkey(self, spec: str) -> str | None:
        try:
            hotkey = parse_hold_hotkey(spec)
        except ValueError as exc:
            return str(exc)
        conflict = shortcut_conflict(self._hotkey, hotkey)
        if conflict:
            return conflict
        error = self._hold_listener.set_hotkey(hotkey.spec)
        if error is None:
            self._hold_hotkey = hotkey
        return error

    def stop(self) -> None:
        self._listener.stop()
        self._hold_listener.stop()

    def join(self, timeout: float | None = None) -> None:
        self._listener.join(timeout)
        self._hold_listener.join(timeout)


def create_hotkeys(
    toggle_spec: str,
    on_toggle: Callable[[], None],
    on_cancel: Callable[[], None],
    hold_spec: str = DEFAULT_HOLD_HOTKEY,
    on_hold_start: Callable[[], None] = lambda: None,
    on_hold_stop: Callable[[], None] = lambda: None,
) -> WindowsHotkeys | PynputHotkeys:
    if os.name == "nt":
        return WindowsHotkeys(
            toggle_spec,
            on_toggle,
            on_cancel,
            hold_spec=hold_spec,
            on_hold_start=on_hold_start,
            on_hold_stop=on_hold_stop,
        )
    return PynputHotkeys(
        toggle_spec,
        on_toggle,
        on_cancel,
        hold_spec=hold_spec,
        on_hold_start=on_hold_start,
        on_hold_stop=on_hold_stop,
    )
