from __future__ import annotations

import logging
from pathlib import Path

from .settings import SettingsStore


LOGGER = logging.getLogger(__name__)


class SoundPlayer:
    """Play optional local WAV cues without delaying recording."""

    def __init__(self, settings: SettingsStore) -> None:
        self._settings = settings

    def play_start(self) -> None:
        settings = self._settings.snapshot()
        if settings.sounds_enabled:
            self.play_file(settings.start_sound_path)

    def play_stop(self) -> None:
        settings = self._settings.snapshot()
        if settings.sounds_enabled:
            self.play_file(settings.stop_sound_path)

    @staticmethod
    def play_file(path_value: str | None) -> None:
        if not path_value:
            return
        path = Path(path_value)
        if not path.is_file() or path.suffix.lower() != ".wav":
            LOGGER.warning("Configured sound is missing or is not a WAV file: %s", path)
            return
        try:
            import winsound

            winsound.PlaySound(
                str(path),
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
        except (ImportError, RuntimeError, OSError):
            LOGGER.exception("Unable to play sound cue: %s", path)

