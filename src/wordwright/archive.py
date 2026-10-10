"""Optional transcript history: one plain Markdown file per day.

Files live in a folder the user picks and look like this::

    # Saturday, October 10, 2026

    ## 14:58:03 · 0:32 · 87 words

    The dictated text...

Markdown is plain text, so the files open in Notepad, render nicely in
Obsidian or VS Code, and can be edited, moved, or deleted freely. Stats are
computed from the entry headings only when the History page is opened;
nothing is sent anywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

TYPING_WORDS_PER_MINUTE = 40
_FILE_NAME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")
_ENTRY = re.compile(r"^## \d{1,2}:\d{2}(?::\d{2})? · (\d+):(\d{2}) · (\d+) words?\s*$")


def day_file(folder: Path, day: date) -> Path:
    return folder / f"{day.isoformat()}.md"


def format_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"{total // 60}:{total % 60:02d}"


class TranscriptArchive:
    """Appends dictations to the day's file in the chosen folder."""

    def __init__(self, now: Callable[[], datetime] = datetime.now) -> None:
        self._now = now

    def save(self, folder: Path | str, text: str, audio_seconds: float) -> Path:
        folder = Path(folder)
        if not folder.is_dir():
            raise FileNotFoundError("The history folder no longer exists.")
        moment = self._now()
        path = day_file(folder, moment.date())
        body = " ".join(text.split())
        words = len(body.split())
        entry = (
            f"## {moment:%H:%M:%S} · {format_duration(audio_seconds)} · "
            f"{words} word{'' if words == 1 else 's'}\n\n{body}\n\n"
        )
        # New day files start with a readable title. Appending in one write
        # keeps entries whole even if the app is closed mid-way.
        header = "" if path.exists() else f"# {moment:%A, %B} {moment.day}, {moment.year}\n\n"
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(header + entry)
        return path


@dataclass
class Totals:
    dictations: int = 0
    words: int = 0
    seconds: float = 0.0

    def add(self, words: int, seconds: float) -> None:
        self.dictations += 1
        self.words += words
        self.seconds += seconds

    @property
    def minutes_saved(self) -> float:
        """Estimated typing time saved, compared with typing at 40 wpm."""

        return max(0.0, self.words / TYPING_WORDS_PER_MINUTE - self.seconds / 60)


@dataclass
class HistoryStats:
    today: Totals = field(default_factory=Totals)
    week: Totals = field(default_factory=Totals)
    all_time: Totals = field(default_factory=Totals)
    days: int = 0


def combine_stats(parts: list[HistoryStats]) -> HistoryStats:
    combined = HistoryStats()
    for part in parts:
        for key in ("today", "week", "all_time"):
            source, target = getattr(part, key), getattr(combined, key)
            target.dictations += source.dictations
            target.words += source.words
            target.seconds += source.seconds
        combined.days += part.days
    return combined


def collect_stats(folder: Path | str, today: date | None = None) -> HistoryStats:
    """Summarize every day file in the folder. Unrecognized lines are ignored,
    so users can edit or annotate the files without breaking anything."""

    today = today or date.today()
    week_start = today - timedelta(days=6)
    stats = HistoryStats()
    folder = Path(folder)
    if not folder.is_dir():
        return stats
    for path in sorted(folder.iterdir()):
        match = _FILE_NAME.match(path.name)
        if not match or not path.is_file():
            continue
        try:
            day = date(*(int(part) for part in match.groups()))
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, ValueError):
            continue
        counted = False
        for line in lines:
            entry = _ENTRY.match(line)
            if not entry:
                continue
            counted = True
            minutes, seconds, words = (int(part) for part in entry.groups())
            duration = minutes * 60 + seconds
            stats.all_time.add(words, duration)
            if day >= week_start and day <= today:
                stats.week.add(words, duration)
            if day == today:
                stats.today.add(words, duration)
        stats.days += counted
    return stats
