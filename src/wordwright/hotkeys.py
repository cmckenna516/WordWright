from __future__ import annotations

from typing import Callable, Any


class GlobalHotkey:
    def __init__(
        self,
        hotkey: str,
        callback: Callable[[], None],
        listener_factory: Callable[..., Any] | None = None,
    ) -> None:
        if listener_factory is None:
            from pynput.keyboard import GlobalHotKeys

            listener_factory = GlobalHotKeys
        self._listener = listener_factory({hotkey: callback})

    def start(self) -> None:
        self._listener.start()

    def wait_until_ready(self) -> None:
        self._listener.wait()

    def stop(self) -> None:
        self._listener.stop()

    def join(self, timeout: float | None = None) -> None:
        self._listener.join(timeout)

