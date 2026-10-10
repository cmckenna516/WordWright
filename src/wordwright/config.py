from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def default_model_directory() -> Path:
    configured = os.environ.get("WORDWRIGHT_MODEL_DIR")
    if configured:
        return Path(configured)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Wordwright" / "models"
    return Path.home() / ".wordwright" / "models"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime settings for Wordwright.

    ``model``, ``device``, and ``compute_type`` are command-line overrides. When
    ``model`` is None, the model comes from Settings (Automatic by default),
    which picks one that suits this machine.
    """

    hotkey: str = "<ctrl>+<alt>+<space>"
    cancel_hotkey: str = "<esc>"
    model: str | None = None
    device: str | None = None
    compute_type: str | None = None
    sample_rate: int = 16_000
    microphone: int | str | None = None
    minimum_recording_seconds: float = 0.25
    typing_delay_seconds: float = 0.15
    hotkey_debounce_seconds: float = 0.5
    model_directory: Path = field(default_factory=default_model_directory)
