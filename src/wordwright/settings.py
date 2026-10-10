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
MAX_HISTORY_FOLDERS = 20
MAX_VOCABULARY_TERM_LENGTH = 60


def default_settings_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Wordwright" / "settings.json"
    return Path.home() / ".wordwright" / "settings.json"


def normalize_folder(path: str | Path) -> str:
    return os.path.normpath(str(path))


def same_folder(first: str, second: str) -> bool:
    return os.path.normcase(normalize_folder(first)) == os.path.normcase(normalize_folder(second))


def folder_labels(folders: tuple[str, ...]) -> dict[str, str]:
    """Short names for the tray and History page: the folder's own name, plus
    its parent when two saved folders share a name."""

    names = {folder: Path(folder).name or folder for folder in folders}
    counts: dict[str, int] = {}
    for name in names.values():
        counts[name.casefold()] = counts.get(name.casefold(), 0) + 1
    return {
        folder: name if counts[name.casefold()] == 1 else f"{name} ({Path(folder).parent})"
        for folder, name in names.items()
    }


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
    # History: folders the user has added, and the one dictations currently go
    # to. None means "don't save" (the default); nothing is written to disk.
    history_folders: tuple[str, ...] = ()
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
        for key in ("vocabulary", "history_folders"):
            if key in changes:
                changes[key] = tuple(changes[key])
        with self._lock:
            candidate = replace(self._settings, **changes)
            self._validate(candidate)
            self._settings = candidate
            self._save(candidate)
            return replace(candidate)

    def add_history_folder(self, folder: str | Path, activate: bool = True) -> UserSettings:
        """Remember a folder (once) and, by default, start saving to it."""

        folder = normalize_folder(folder)
        with self._lock:
            current = self._settings
            existing = next((f for f in current.history_folders if same_folder(f, folder)), None)
            folders = current.history_folders if existing else (*current.history_folders, folder)
            chosen = existing or folder
            return self.update(
                history_folders=folders,
                history_folder=chosen if activate else current.history_folder,
            )

    def remove_history_folder(self, folder: str) -> UserSettings:
        """Forget a folder. Its files are left untouched."""

        with self._lock:
            current = self._settings
            folders = tuple(f for f in current.history_folders if not same_folder(f, folder))
            active = current.history_folder
            if active is not None and same_folder(active, folder):
                active = None
            return self.update(history_folders=folders, history_folder=active)

    def set_history_destination(self, folder: str | None) -> UserSettings:
        """Choose where dictations go; None stops saving."""

        with self._lock:
            if folder is None:
                return self.update(history_folder=None)
            match = next(
                (f for f in self._settings.history_folders if same_folder(f, folder)), None
            )
            if match is None:
                raise ValueError("That folder hasn't been added to Wordwright.")
            return self.update(history_folder=match)

    @staticmethod
    def _migrate(raw: dict[str, Any]) -> dict[str, Any]:
        """Settings from 0.2 test builds used one folder plus an on/off flag."""

        if "history_enabled" not in raw:
            return raw
        migrated = dict(raw)
        enabled = bool(migrated.pop("history_enabled"))
        folder = migrated.get("history_folder")
        if folder:
            folders = list(migrated.get("history_folders") or [])
            if not any(same_folder(f, folder) for f in folders):
                folders.append(folder)
            migrated["history_folders"] = folders
        if not enabled:
            migrated["history_folder"] = None
        return migrated

    def _load(self) -> UserSettings:
        if not self._path.is_file():
            return UserSettings()
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return UserSettings()
        if not isinstance(raw, dict):
            return UserSettings()
        raw = self._migrate(raw)
        known = {
            key: tuple(value)
            if key in {"vocabulary", "history_folders"} and isinstance(value, list)
            else value
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
        # The active folder must come after the folder list it refers to.
        for key, value in sorted(known.items(), key=lambda item: item[0] == "history_folder"):
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
        if len(settings.history_folders) > MAX_HISTORY_FOLDERS:
            raise ValueError(f"Wordwright can remember up to {MAX_HISTORY_FOLDERS} folders.")
        for folder in settings.history_folders:
            if not isinstance(folder, str) or not folder.strip():
                raise ValueError("History folders must be folder paths.")
        if settings.history_folder is not None and not any(
            same_folder(settings.history_folder, f) for f in settings.history_folders
        ):
            raise ValueError("Add a folder before saving dictations to it.")
