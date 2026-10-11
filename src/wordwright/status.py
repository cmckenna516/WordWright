from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Any

from PIL import Image, ImageDraw

from .overlay import RecordingOverlay
from .settings import SettingsStore
from .sounds import SoundPlayer
from .state import AppState
from .theme import theme_for

__all__ = ["AppState", "TrayStatus", "make_status_icon"]


def logo_path() -> Path:
    return Path(__file__).with_name("assets") / "logo-scroll-v2.png"


def load_logo(size: int = 52) -> Image.Image | None:
    path = logo_path()
    if not path.is_file():
        return None
    logo = Image.open(path).convert("RGBA")
    logo.thumbnail((size, size), Image.Resampling.LANCZOS)
    return logo


def make_status_icon(
    state: AppState,
    size: int = 64,
    logo: Image.Image | None = None,
) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if logo is not None:
        x = (size - logo.width) // 2
        y = (size - logo.height) // 2
        image.alpha_composite(logo, (x, y))
        badge_size = max(16, size // 3)
        draw.ellipse(
            (size - badge_size, size - badge_size, size - 2, size - 2),
            fill=theme_for(state).tray_rgb + (255,),
            outline=(245, 245, 245, 255),
            width=2,
        )
    else:
        margin = max(3, size // 12)
        draw.ellipse(
            (margin, margin, size - margin, size - margin),
            fill=theme_for(state).tray_rgb + (255,),
            outline=(245, 245, 245, 255),
            width=max(2, size // 16),
        )
    return image


class TrayStatus:
    """System-tray status display that does not take typing focus."""

    def __init__(self, settings: SettingsStore | None = None) -> None:
        import pystray

        self._pystray = pystray
        self._settings = settings or SettingsStore()
        self._sounds = SoundPlayer(self._settings)
        self._state = AppState.LOADING
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._quit_callback: Callable[[], None] | None = None
        self._toggle_callback: Callable[[], None] | None = None
        self._model_change_callback: Callable[[], None] | None = None
        self._model_explainer: Callable[[], str] = lambda: ""
        self._hotkey_changer: Callable[[str], str | None] = lambda spec: None
        self._logo = load_logo()
        self._overlay = (
            RecordingOverlay(
                logo_path(),
                settings=self._settings,
                sounds=self._sounds,
                on_toggle=self._toggle,
                on_quit=self._request_quit,
                on_model_changed=self._model_changed,
                model_explainer=lambda: self._model_explainer(),
                hotkey_changer=lambda spec: self._hotkey_changer(spec),
            )
            if self._logo is not None
            else None
        )
        self._icon = pystray.Icon(
            "Wordwright",
            make_status_icon(self._state, logo=self._logo),
            self._title(self._state),
            menu=pystray.Menu(
                pystray.MenuItem("Open Wordwright", self._open),
                pystray.MenuItem(self._menu_status, None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Show overlay at all times",
                    self._toggle_overlay_visibility,
                    checked=self._overlay_checked,
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit Wordwright", self._quit),
            ),
        )

    def set_quit_callback(self, callback: Callable[[], None]) -> None:
        self._quit_callback = callback

    def set_toggle_callback(self, callback: Callable[[], None]) -> None:
        self._toggle_callback = callback

    def set_model_change_callback(self, callback: Callable[[], None]) -> None:
        self._model_change_callback = callback

    def set_model_explainer(self, explainer: Callable[[], str]) -> None:
        self._model_explainer = explainer

    def set_hotkey_changer(self, changer: Callable[[str], str | None]) -> None:
        self._hotkey_changer = changer

    def set_model_label(self, label: str) -> None:
        if self._overlay is not None:
            self._overlay.set_model_label(label)

    def update(self, state: AppState) -> None:
        with self._lock:
            previous = self._state
            self._state = state
            self._icon.icon = make_status_icon(state, logo=self._logo)
            self._icon.title = self._title(state)
        if state is AppState.RECORDING and previous is not AppState.RECORDING:
            self._sounds.play_start()
        elif previous is AppState.RECORDING and state is not AppState.RECORDING:
            self._sounds.play_stop()
        if self._overlay is not None:
            self._overlay.update(state)
        self._icon.update_menu()

    def notify(self, message: str, title: str = "Wordwright") -> None:
        try:
            self._icon.notify(message, title)
        except (AttributeError, NotImplementedError):
            pass

    def run(self) -> None:
        if self._overlay is None:
            self._icon.run()
            return
        self._icon.run_detached()
        overlay_completed = self._overlay.run()
        if not overlay_completed and not self._stop_event.is_set():
            self.notify(
                "The launcher and overlay could not start. Wordwright remains available in the tray."
            )
            self._stop_event.wait()

    def stop(self) -> None:
        self._stop_event.set()
        if self._overlay is not None:
            self._overlay.stop()
        self._icon.stop()

    def _menu_status(self, item: Any) -> str:
        del item
        with self._lock:
            return f"Status: {self._state.value}"

    def _quit(self, icon: Any, item: Any) -> None:
        del icon, item
        self._request_quit()

    def _request_quit(self) -> None:
        if self._quit_callback:
            self._quit_callback()

    def _toggle(self) -> None:
        if self._toggle_callback:
            self._toggle_callback()

    def _model_changed(self) -> None:
        if self._model_change_callback:
            self._model_change_callback()

    def _open(self, icon: Any, item: Any) -> None:
        del icon, item
        if self._overlay is not None:
            self._overlay.show_launcher()

    def _overlay_checked(self, item: Any) -> bool:
        del item
        return self._settings.snapshot().show_overlay_always

    def _toggle_overlay_visibility(self, icon: Any, item: Any) -> None:
        del icon, item
        current = self._settings.snapshot().show_overlay_always
        self._settings.update(show_overlay_always=not current)
        if self._overlay is not None:
            self._overlay.settings_changed()
        self._icon.update_menu()

    @staticmethod
    def _title(state: AppState) -> str:
        return f"Wordwright — {state.value}"
