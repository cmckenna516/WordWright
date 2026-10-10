from __future__ import annotations

from dataclasses import dataclass

from .state import AppState


@dataclass(frozen=True, slots=True)
class StateTheme:
    """Copy and colors for one state, shared by the tray, overlay, and launcher."""

    overlay_label: str
    launcher_copy: str
    accent: str
    overlay_fill: str
    overlay_border: str
    tray_rgb: tuple[int, int, int]


STATE_THEME: dict[AppState, StateTheme] = {
    AppState.LOADING: StateTheme(
        "LOADING MODEL", "Preparing the local scribe…",
        "#e1b75e", "#352b16", "#9f7837", (230, 165, 30),
    ),
    AppState.IDLE: StateTheme(
        "READY", "Ready to write",
        "#a9c596", "#181a19", "#705d36", (110, 118, 129),
    ),
    AppState.RECORDING: StateTheme(
        "RECORDING", "Recording · Esc cancels",
        "#f08b7e", "#3b1715", "#b45348", (220, 45, 55),
    ),
    AppState.TRANSCRIBING: StateTheme(
        "TRANSCRIBING", "Setting your words in type…",
        "#78b8e9", "#14263a", "#477eae", (35, 125, 225),
    ),
    AppState.SUCCESS: StateTheme(
        "TEXT TYPED", "Typed at your cursor",
        "#79c78b", "#18301f", "#4a8c5b", (35, 165, 90),
    ),
    AppState.CLIPBOARD: StateTheme(
        "COPIED TO CLIPBOARD", "No text field found — copied to clipboard",
        "#e1b75e", "#352b16", "#9f7837", (201, 153, 65),
    ),
    AppState.ERROR: StateTheme(
        "ERROR", "Something needs attention",
        "#d98bd9", "#351634", "#954a91", (180, 35, 190),
    ),
}


def theme_for(state: AppState | str) -> StateTheme:
    """Look up a state's theme, falling back to Idle for unknown values."""

    try:
        return STATE_THEME[AppState(state)]
    except ValueError:
        return STATE_THEME[AppState.IDLE]
