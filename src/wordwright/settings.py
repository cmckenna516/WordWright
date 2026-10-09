from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any


def default_settings_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Wordwright" / "settings.json"
    return Path.home() / ".wordwright" / "settings.json"


@dataclass(frozen=True, slots=True)
class UserSettings:
    """User-controlled preferences that are safe to persist locally."""

    show_overlay_always: bool = True
    overlay_position: str = "top_center"
    sounds_enabled: bool = False
    start_sound_path: str | None = None
    stop_sound_path: str | None = None
    launch_at_sign_in: bool = False
    history_enabled: bool = False
    history_folder: str | None = None
    history_retention_days: int | None = 30
    correction_learning_enabled: bool = False
    mind_map_enabled: bool = False


class SettingsStore:
    """Thread-safe JSON settings store with privacy-safe defaults."""

    _POSITIONS = {"top_center", "bottom_center", "left_center", "right_center"}
    _RETENTION_DAYS = {30, 60, 90, None}

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_settings_path()
        self._lock = threading.RLock()
        self._settings = self._load()

    @property
    def path(self) -> Path:
        return self._path

    def snapshot(self) -> UserSettings:
        with self._lock:
            return replace(self._settings)

    def update(self, **changes: Any) -> UserSettings:
        with self._lock:
            candidate = replace(self._settings, **changes)
            self._validate(candidate)
            self._settings = candidate
            self._save(candidate)
            return replace(candidate)

    def _load(self) -> UserSettings:
        if not self._path.is_file():
            return UserSettings()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            known = {
                key: value
                for key, value in raw.items()
                if key in UserSettings.__dataclass_fields__
            }
            settings = UserSettings(**known)
            self._validate(settings)
            return settings
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return UserSettings()

    def _save(self, settings: UserSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(settings), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self._path)

    def _validate(self, settings: UserSettings) -> None:
        if settings.overlay_position not in self._POSITIONS:
            raise ValueError(f"Unsupported overlay position: {settings.overlay_position}")
        if settings.history_retention_days not in self._RETENTION_DAYS:
            raise ValueError("History retention must be 30, 60, 90 days, or never.")
        if settings.history_enabled and not settings.history_folder:
            raise ValueError("A local folder is required before history can be enabled.")
        if settings.correction_learning_enabled and not settings.history_enabled:
            raise ValueError("Correction learning requires local history to be enabled.")
        if settings.mind_map_enabled and not settings.history_enabled:
            raise ValueError("Mind maps require local history to be enabled.")

