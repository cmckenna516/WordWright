from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from wordwright.archive import TranscriptArchive, collect_stats, combine_stats


def fixed(*moment):
    return lambda: datetime(*moment)


class TranscriptArchiveTests(unittest.TestCase):
    def test_writes_one_readable_markdown_file_per_day(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            TranscriptArchive(fixed(2026, 10, 10, 14, 58, 3)).save(folder, "Hello there\nworld.", 32.4)
            TranscriptArchive(fixed(2026, 10, 10, 15, 1, 0)).save(folder, "One", 1.0)
            TranscriptArchive(fixed(2026, 10, 11, 9, 0, 0)).save(folder, "Next day", 2.0)

            first = (Path(folder) / "2026-10-10.md").read_text(encoding="utf-8")
            files = sorted(p.name for p in Path(folder).iterdir())

        self.assertEqual(files, ["2026-10-10.md", "2026-10-11.md"])
        self.assertEqual(
            first,
            "# Saturday, October 10, 2026\n\n"
            "## 14:58:03 · 0:32 · 3 words\n\nHello there world.\n\n"
            "## 15:01:00 · 0:01 · 1 word\n\nOne\n\n",
        )

    def test_missing_folder_raises_instead_of_creating_one(self) -> None:
        with tempfile.TemporaryDirectory() as parent:
            gone = Path(parent) / "unplugged-drive"
            with self.assertRaises(FileNotFoundError):
                TranscriptArchive().save(gone, "text", 1.0)
            self.assertFalse(gone.exists())


class StatsTests(unittest.TestCase):
    def test_totals_for_today_week_and_all_time(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            for moment, words, seconds in (
                ((2026, 10, 10, 9, 0, 0), 120, 60),
                ((2026, 10, 10, 10, 0, 0), 40, 15),
                ((2026, 10, 5, 9, 0, 0), 10, 5),
                ((2026, 9, 1, 9, 0, 0), 30, 12),
            ):
                TranscriptArchive(fixed(*moment)).save(folder, " ".join(["w"] * words), seconds)
            stats = collect_stats(folder, today=date(2026, 10, 10))

        self.assertEqual((stats.today.dictations, stats.today.words, stats.today.seconds), (2, 160, 75))
        self.assertEqual((stats.week.dictations, stats.week.words), (3, 170))
        self.assertEqual((stats.all_time.dictations, stats.all_time.words), (4, 200))
        self.assertEqual(stats.days, 3)
        # 160 words at 40 wpm = 4 min of typing, minus 1.25 min of speaking.
        self.assertAlmostEqual(stats.today.minutes_saved, 2.75)

    def test_user_edits_and_other_files_are_tolerated(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "2026-10-10.md"
            path.write_text(
                "# My notes\n\nSome thoughts I typed myself.\n\n"
                "## 14:58:03 · 0:32 · 87 words\n\nText I later edited.\n\n"
                "## not an entry\n",
                encoding="utf-8",
            )
            (Path(folder) / "shopping.md").write_text("## 1:00 · 0:01 · 999 words\n", encoding="utf-8")
            (Path(folder) / "2026-13-45.md").write_text("## 1:00 · 0:01 · 5 words\n", encoding="utf-8")
            stats = collect_stats(folder, today=date(2026, 10, 10))

        self.assertEqual((stats.all_time.dictations, stats.all_time.words), (1, 87))

    def test_folders_stay_separate_and_stats_combine(self) -> None:
        with tempfile.TemporaryDirectory() as projects, tempfile.TemporaryDirectory() as meetings:
            TranscriptArchive(fixed(2026, 10, 10, 9, 0, 0)).save(projects, "project note", 3)
            TranscriptArchive(fixed(2026, 10, 10, 9, 5, 0)).save(meetings, "meeting note here", 4)
            project_text = (Path(projects) / "2026-10-10.md").read_text(encoding="utf-8")
            stats = combine_stats(
                [collect_stats(folder, today=date(2026, 10, 10)) for folder in (projects, meetings)]
            )

        self.assertIn("project note", project_text)
        self.assertNotIn("meeting note", project_text)
        self.assertEqual((stats.today.dictations, stats.today.words), (2, 5))

    def test_missing_folder_gives_empty_stats(self) -> None:
        self.assertEqual(collect_stats("/no/such/folder").all_time.dictations, 0)


if __name__ == "__main__":
    unittest.main()
