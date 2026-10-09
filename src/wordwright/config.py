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
    """Runtime settings for the first Wordwright prototype."""

    hotkey: str = "<ctrl>+<alt>+<space>"
    model: str = "small.en"
    device: str = "cpu"
    compute_type: str = "int8"
    sample_rate: int = 16_000
    microphone: int | str | None = None
    minimum_recording_seconds: float = 0.25
    paste_delay_seconds: float = 0.15
    hotkey_debounce_seconds: float = 0.5
    model_directory: Path = field(default_factory=default_model_directory)

