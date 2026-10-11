from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from .hardware import AUTO, MODEL_CHOICES
from .hotkeys import DEFAULT_HOTKEY, parse_hotkey

MAX_VOCABULARY_TERMS = 200
MAX_VOCABULARY_TERM_LENGTH = 60


def default_settings_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Wordwright" / "settings.json"
    return Path.home() / ".wordwright" / "settings.json"


def parse_vocabulary(text: str) -> tuple[str, ...]:
    """Split user-entered vocabulary on new lines or commas, de-duplicated."""

    terms: list[str] = []
    seen: set[str] = set()
    for raw in re.split(r"[\n,]", text):
        term = " ".join(raw.split())
        if term and term.casefold() not in seen:
            seen.add(term.casefold())
            terms.append(term)
    return tuple(terms)


@dataclass(frozen=True, slots=True)
class UserSettings:
    """User-controlled preferences that are safe to persist locally."""

    show_overlay_always: bool = True
    overlay_position: str = "top_center"
    sounds_enabled: bool = False
    start_sound_path: str | None = None
    stop_sound_path: str | None = None
    hotkey: str = DEFAULT_HOTKEY
    model_choice: str = AUTO
    vocabulary: tuple[str, ...] = ()
    # Reserved for the planned running transcript archive. Off until the user
    # chooses a folder; nothing is written to disk while this is off.
    history_enabled: bool = False
    history_folder: str | None = None


class SettingsStore:
    """Thread-safe JSON settings store with privacy-safe defaults."""

    _POSITIONS = {"top_center", "bottom_center", "left_center", "right_center"}

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
        if "vocabulary" in changes:
            changes["vocabulary"] = tuple(changes["vocabulary"])
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
        except (OSError, ValueError, json.JSONDecodeError):
            return UserSettings()
        if not isinstance(raw, dict):
            return UserSettings()
        known = {
            key: tuple(value) if key == "vocabulary" and isinstance(value, list) else value
            for key, value in raw.items()
            if key in UserSettings.__dataclass_fields__
        }
        try:
            settings = UserSettings(**known)
            self._validate(settings)
            return settings
        except (TypeError, ValueError):
            pass
        # Fall back to field by field so one bad value never wipes out the
        # rest of the user's preferences.
        settings = UserSettings()
        for key, value in known.items():
            try:
                candidate = replace(settings, **{key: value})
                self._validate(candidate)
            except (TypeError, ValueError):
                continue
            settings = candidate
        return settings

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
        parse_hotkey(settings.hotkey)
        if settings.model_choice not in MODEL_CHOICES:
            raise ValueError(f"Unsupported speech model: {settings.model_choice}")
        if len(settings.vocabulary) > MAX_VOCABULARY_TERMS:
            raise ValueError(f"Vocabulary is limited to {MAX_VOCABULARY_TERMS} terms.")
        for term in settings.vocabulary:
            if not isinstance(term, str) or not term.strip():
                raise ValueError("Vocabulary terms must be non-empty text.")
            if len(term) > MAX_VOCABULARY_TERM_LENGTH:
                raise ValueError(
                    f"Vocabulary terms are limited to {MAX_VOCABULARY_TERM_LENGTH} characters."
                )
        if settings.history_enabled and not settings.history_folder:
            raise ValueError("A local folder is required before history can be enabled.")
