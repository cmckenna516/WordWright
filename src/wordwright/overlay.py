from __future__ import annotations

import ctypes
import logging
import os
import queue
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

from .hotkeys import hotkey_label
from .settings import SettingsStore
from .sounds import SoundPlayer
from .state import AppState
from .theme import theme_for


LOGGER = logging.getLogger(__name__)


class _Rect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _Rect),
        ("rcWork", _Rect),
        ("dwFlags", wintypes.DWORD),
    ]


class RecordingOverlay:
    """Persistent, focus-safe Wordwright scroll and status display."""

    _WIDTH = 456
    _HEIGHT = 76
    _ACTIVE_TICK_MS = 125
    _IDLE_TICK_MS = 250
    _ANIMATED_STATES = {AppState.RECORDING.value, AppState.TRANSCRIBING.value}

    def __init__(
        self,
        logo_path: Path,
        settings: SettingsStore | None = None,
        sounds: SoundPlayer | None = None,
        on_toggle: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
        on_model_changed: Callable[[], None] | None = None,
        model_explainer: Callable[[], str] | None = None,
        hotkey_changer: Callable[[str], str | None] | None = None,
        canvas_width: int = _WIDTH,
        canvas_height: int = _HEIGHT,
    ) -> None:
        self._logo_path = logo_path
        self._settings = settings or SettingsStore()
        self._sounds = sounds or SoundPlayer(self._settings)
        self._on_toggle = on_toggle or (lambda: None)
        self._on_quit = on_quit or (lambda: None)
        self._on_model_changed = on_model_changed or (lambda: None)
        self._model_explainer = model_explainer or (lambda: "")
        self._hotkey_changer = hotkey_changer or (lambda spec: None)
        self._canvas_width = canvas_width
        self._canvas_height = canvas_height
        self._updates: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._enable_dpi_awareness()

    def set_callbacks(
        self,
        on_toggle: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_toggle = on_toggle
        self._on_quit = on_quit

    def update(self, state: Any) -> None:
        value = getattr(state, "value", str(state))
        self._updates.put(("state", str(value)))

    def show_launcher(self) -> None:
        self._updates.put(("show_launcher", None))

    def settings_changed(self) -> None:
        self._updates.put(("settings_changed", None))

    def set_model_label(self, label: str) -> None:
        self._updates.put(("model_label", label))

    def stop(self) -> None:
        self._updates.put(("stop", None))

    def run(self) -> bool:
        try:
            self._run_tk()
            return True
        except Exception:
            LOGGER.exception("Recording overlay stopped unexpectedly")
            return False

    def _run_tk(self) -> None:
        import tkinter as tk
        from .launcher import LauncherWindow

        root = tk.Tk()
        launcher = LauncherWindow(
            root=root,
            settings=self._settings,
            sounds=self._sounds,
            on_toggle=lambda: self._on_toggle(),
            on_quit=lambda: self._on_quit(),
            on_settings_changed=self.settings_changed,
            on_model_changed=lambda: self._on_model_changed(),
            model_explainer=lambda: self._model_explainer(),
            hotkey_changer=lambda spec: self._hotkey_changer(spec),
        )

        window = tk.Toplevel(root)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        transparent = "#ff00ff"
        window.configure(bg=transparent)
        try:
            window.wm_attributes("-transparentcolor", transparent)
        except tk.TclError:
            LOGGER.warning("This Tk build does not support transparent-color windows")

        canvas = tk.Canvas(
            window,
            width=self._canvas_width,
            height=self._canvas_height,
            bg=transparent,
            highlightthickness=0,
            borderwidth=0,
        )
        canvas.pack()
        window.geometry(f"{self._canvas_width}x{self._canvas_height}+0+0")
        window.update_idletasks()
        wrapper_handle = self._make_focus_safe(window.winfo_id())

        state = AppState.LOADING.value
        launcher.update_state(state)
        stopped = False
        visible = False
        menu_open = False
        menu_expires_at = 0.0
        animation_frame = 0
        last_position: tuple[int, int, str] | None = None
        last_render: tuple[Any, ...] | None = None

        def launcher_visible() -> bool:
            return launcher.is_visible()

        def expanded() -> bool:
            return state != AppState.IDLE.value or menu_open or launcher_visible()

        def animating() -> bool:
            return state in self._ANIMATED_STATES

        def render_key() -> tuple[Any, ...]:
            # Everything the drawing depends on. The canvas is redrawn only when
            # this changes, so an idle overlay costs almost nothing.
            phase = (animation_frame // 4) % 2 if animating() else 0
            return (state, menu_open, expanded(), phase, self._settings.snapshot().hotkey)

        def apply_visibility() -> None:
            nonlocal visible
            settings = self._settings.snapshot()
            should_show = settings.show_overlay_always or state != AppState.IDLE.value
            if should_show and not visible:
                window.deiconify()
                window.lift()
                visible = True
            elif not should_show and visible:
                window.withdraw()
                visible = False

        def place_overlay(force: bool = False) -> None:
            nonlocal last_position
            settings = self._settings.snapshot()
            work_area = self._active_work_area(root)
            x, y = self._position_for_work_area(work_area, settings.overlay_position)
            marker = (x, y, settings.overlay_position)
            if force or marker != last_position:
                window.geometry(
                    f"{self._canvas_width}x{self._canvas_height}+{x}+{y}"
                )
                last_position = marker

        def draw_rolls(left: int, top: int, right: int, bottom: int) -> None:
            canvas.create_oval(
                left - 7,
                top - 4,
                left + 6,
                bottom + 4,
                fill="#bd9349",
                outline="#493313",
                width=1,
            )
            canvas.create_oval(
                right - 6,
                top - 4,
                right + 7,
                bottom + 4,
                fill="#bd9349",
                outline="#493313",
                width=1,
            )

        def draw_quill(x: int, y: int, moving: bool) -> None:
            offset = -4 if moving and (animation_frame // 4) % 2 == 0 else 4 if moving else 0
            canvas.create_line(
                x - 8 + offset,
                y + 9,
                x + 8 + offset,
                y - 9,
                fill="#d6a84b",
                width=2,
            )
            canvas.create_line(
                x - 1 + offset,
                y + 1,
                x + 11 + offset,
                y - 11,
                fill="#d6a84b",
                width=5,
            )
            canvas.create_line(x - 11, y + 12, x + 15, y + 12, fill="#9a7035")

        def draw_closed_scroll() -> None:
            center_x = self._canvas_width // 2
            center_y = self._canvas_height // 2
            canvas.create_rectangle(
                center_x - 14,
                center_y - 4,
                center_x + 14,
                center_y + 4,
                fill="#b98d43",
                outline="#624920",
            )
            canvas.create_oval(
                center_x - 20,
                center_y - 9,
                center_x - 11,
                center_y + 9,
                fill="#caa354",
                outline="#503918",
            )
            canvas.create_oval(
                center_x + 11,
                center_y - 9,
                center_x + 20,
                center_y + 9,
                fill="#caa354",
                outline="#503918",
            )

        def draw_status() -> None:
            label, background, border, foreground = self._display_for_state(state)
            left, top, right, bottom = 15, 15, self._canvas_width - 15, 61
            canvas.create_rectangle(
                left,
                top,
                right,
                bottom,
                fill=background,
                outline=border,
                width=1,
            )
            draw_rolls(left, top, right, bottom)
            draw_quill(51, 38, animating())
            canvas.create_text(
                83,
                29,
                text="WORDWRIGHT",
                fill="#9b927f",
                font=("Courier New", 7),
                anchor="w",
            )
            canvas.create_text(
                83,
                45,
                text=label,
                fill=foreground,
                font=("Courier New", 9, "bold"),
                anchor="w",
            )
            shortcut = hotkey_label(self._settings.snapshot().hotkey).upper().replace("+", " · ")
            hint = "ESC TO CANCEL" if state == AppState.RECORDING.value else shortcut
            canvas.create_text(
                right - 17,
                38,
                text=hint,
                fill="#7f8079",
                font=("Courier New", 7),
                anchor="e",
            )

        def draw_menu() -> None:
            left, top, right, bottom = 15, 15, self._canvas_width - 15, 61
            canvas.create_rectangle(
                left,
                top,
                right,
                bottom,
                fill="#181a19",
                outline="#705d36",
                width=1,
            )
            draw_rolls(left, top, right, bottom)
            draw_quill(45, 38, False)
            canvas.create_text(72, 29, text="WORDWRIGHT", fill="#9b927f", font=("Courier New", 7), anchor="w")
            canvas.create_text(72, 45, text="QUICK COMMAND", fill="#d8ccb0", font=("Courier New", 7, "bold"), anchor="w")

            canvas.create_rectangle(185, 24, 315, 52, fill="#d6a84b", outline="#e5c16d", tags="start")
            canvas.create_text(250, 38, text="●  START RECORDING", fill="#1b160b", font=("Courier New", 7, "bold"), tags="start")
            canvas.create_rectangle(323, 24, 422, 52, fill="#242624", outline="#4b4b43", tags="open")
            canvas.create_text(372, 38, text="OPEN APP", fill="#cbc5b5", font=("Courier New", 7), tags="open")

        def redraw() -> None:
            nonlocal last_render
            last_render = render_key()
            canvas.delete("all")
            if menu_open:
                draw_menu()
            elif expanded():
                draw_status()
            else:
                draw_closed_scroll()

        def click(event: Any) -> None:
            nonlocal menu_open, menu_expires_at
            if state != AppState.IDLE.value:
                return
            if not menu_open:
                menu_open = True
                menu_expires_at = time.monotonic() + 8.0
                redraw()
                return
            action = self._menu_action_at(event.x, event.y)
            if action == "record":
                menu_open = False
                self._on_toggle()
            elif action == "open":
                menu_open = False
                launcher.show()
                redraw()
            else:
                menu_open = False
                redraw()

        canvas.bind("<Button-1>", click)

        mouse_listener = None
        try:
            from pynput import mouse

            def global_click(x: int, y: int, button: Any, pressed: bool) -> None:
                del button
                if not pressed or not menu_open or last_position is None:
                    return
                origin_x, origin_y, _ = last_position
                if not self._point_in_scroll(x, y, origin_x, origin_y):
                    self._updates.put(("collapse_menu", None))

            mouse_listener = mouse.Listener(on_click=global_click)
            mouse_listener.start()
        except Exception:
            LOGGER.exception("Unable to start click-away monitoring for the overlay")

        def tick() -> None:
            nonlocal state, stopped, menu_open, menu_expires_at, animation_frame
            settings_were_changed = False
            while True:
                try:
                    action, payload = self._updates.get_nowait()
                except queue.Empty:
                    break
                if action == "stop":
                    stopped = True
                    break
                if action == "state":
                    state = str(payload)
                    if state != AppState.IDLE.value:
                        menu_open = False
                    launcher.update_state(state)
                elif action == "model_label":
                    launcher.set_model_label(str(payload))
                elif action == "show_launcher":
                    menu_open = False
                    launcher.show()
                elif action == "settings_changed":
                    settings_were_changed = True
                elif action == "collapse_menu":
                    menu_open = False

            if stopped:
                if mouse_listener is not None:
                    mouse_listener.stop()
                window.destroy()
                root.destroy()
                return
            if menu_open and time.monotonic() >= menu_expires_at:
                menu_open = False

            if render_key() != last_render:
                redraw()
            apply_visibility()
            if animation_frame % 4 == 0 or settings_were_changed:
                place_overlay(force=settings_were_changed)
                if visible and os.name == "nt":
                    self._keep_topmost(wrapper_handle)
            animation_frame += 1
            busy = animating() or menu_open or state != AppState.IDLE.value
            root.after(self._ACTIVE_TICK_MS if busy else self._IDLE_TICK_MS, tick)

        place_overlay(force=True)
        apply_visibility()
        root.after(0, tick)
        root.mainloop()
        if mouse_listener is not None:
            mouse_listener.stop()

    @staticmethod
    def _display_for_state(state: str) -> tuple[str, str, str, str]:
        theme = theme_for(state)
        return theme.overlay_label, theme.overlay_fill, theme.overlay_border, theme.accent

    @staticmethod
    def _menu_action_at(x: int, y: int) -> str | None:
        if not 24 <= y <= 52:
            return None
        if 185 <= x <= 315:
            return "record"
        if 323 <= x <= 422:
            return "open"
        return None

    def _point_in_scroll(
        self,
        x: int,
        y: int,
        origin_x: int,
        origin_y: int,
    ) -> bool:
        return (
            origin_x + 15 <= x <= origin_x + self._canvas_width - 15
            and origin_y + 15 <= y <= origin_y + 61
        )

    def _position_for_work_area(
        self,
        work_area: tuple[int, int, int, int],
        position: str,
    ) -> tuple[int, int]:
        left, top, right, bottom = work_area
        center_x = left + (right - left - self._canvas_width) // 2
        center_y = top + (bottom - top - self._canvas_height) // 2
        margin = 8
        if position == "bottom_center":
            return center_x, bottom - self._canvas_height - margin
        if position == "left_center":
            return left + margin, center_y
        if position == "right_center":
            return right - self._canvas_width - margin, center_y
        return center_x, top + margin

    @staticmethod
    def _active_work_area(root: Any) -> tuple[int, int, int, int]:
        if os.name != "nt":
            return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
        try:
            user32 = ctypes.windll.user32
            get_foreground = user32.GetForegroundWindow
            get_foreground.restype = wintypes.HWND
            monitor_from_window = user32.MonitorFromWindow
            monitor_from_window.argtypes = [wintypes.HWND, wintypes.DWORD]
            monitor_from_window.restype = wintypes.HANDLE
            get_monitor_info = user32.GetMonitorInfoW
            get_monitor_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MonitorInfo)]
            get_monitor_info.restype = wintypes.BOOL
            foreground = get_foreground()
            monitor = monitor_from_window(foreground, 2)
            info = _MonitorInfo()
            info.cbSize = ctypes.sizeof(_MonitorInfo)
            if monitor and get_monitor_info(monitor, ctypes.byref(info)):
                work = info.rcWork
                return work.left, work.top, work.right, work.bottom
        except (AttributeError, OSError):
            LOGGER.exception("Unable to determine the active monitor work area")
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()

    @staticmethod
    def _make_focus_safe(window_handle: int) -> int:
        if os.name != "nt":
            return window_handle
        user32 = ctypes.windll.user32
        get_parent = user32.GetParent
        get_parent.argtypes = [wintypes.HWND]
        get_parent.restype = wintypes.HWND
        wrapper_handle = get_parent(window_handle) or window_handle
        get_window_long = user32.GetWindowLongPtrW
        set_window_long = user32.SetWindowLongPtrW
        get_window_long.argtypes = [wintypes.HWND, ctypes.c_int]
        get_window_long.restype = ctypes.c_ssize_t
        set_window_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        set_window_long.restype = ctypes.c_ssize_t
        extended_style = get_window_long(wrapper_handle, -20)
        extended_style &= ~0x00000020  # WS_EX_TRANSPARENT: retain mouse clicks.
        extended_style |= 0x00000080 | 0x08000000  # TOOLWINDOW | NOACTIVATE.
        set_window_long(wrapper_handle, -20, extended_style)
        RecordingOverlay._keep_topmost(wrapper_handle, frame_changed=True)
        return int(wrapper_handle)

    @staticmethod
    def _keep_topmost(window_handle: int, frame_changed: bool = False) -> None:
        if os.name != "nt":
            return
        flags = 0x0001 | 0x0002 | 0x0010
        if frame_changed:
            flags |= 0x0020
        set_window_pos = ctypes.windll.user32.SetWindowPos
        set_window_pos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        set_window_pos.restype = wintypes.BOOL
        set_window_pos(window_handle, -1, 0, 0, 0, 0, flags)

    @staticmethod
    def _enable_dpi_awareness() -> None:
        if os.name != "nt":
            return
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except (AttributeError, OSError):
                pass
