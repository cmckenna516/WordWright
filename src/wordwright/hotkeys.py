from __future__ import annotations

from typing import Any, Callable, Mapping


class GlobalHotkey:
    """System-wide hotkeys. Keys still reach the focused app; none are swallowed."""

    def __init__(
        self,
        bindings: Mapping[str, Callable[[], None]],
        listener_factory: Callable[..., Any] | None = None,
    ) -> None:
        if listener_factory is None:
            from pynput.keyboard import GlobalHotKeys

            listener_factory = GlobalHotKeys
        self._listener = listener_factory(dict(bindings))

    def start(self) -> None:
        self._listener.start()

    def wait_until_ready(self) -> None:
        self._listener.wait()

    def stop(self) -> None:
        self._listener.stop()

    def join(self, timeout: float | None = None) -> None:
        self._listener.join(timeout)
