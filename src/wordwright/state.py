from __future__ import annotations

from enum import Enum


class AppState(str, Enum):
    """Every state the controller, tray, overlay, and launcher can show."""

    LOADING = "Loading model"
    IDLE = "Idle"
    RECORDING = "Recording"
    TRANSCRIBING = "Transcribing"
    SUCCESS = "Text typed"
    CLIPBOARD = "Copied to clipboard"
    SAVED = "Saved to history"
    ERROR = "Error"
