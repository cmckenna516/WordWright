from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wordwright.settings import SettingsStore

from wordwright.overlay import RecordingOverlay


class RecordingOverlayTests(unittest.TestCase):
    def test_status_copy_matches_approved_wordwright_states(self) -> None:
        self.assertEqual(
            RecordingOverlay._display_for_state("Recording")[0],
            "RECORDING",
        )
        self.assertEqual(
            RecordingOverlay._display_for_state("Transcribing")[0],
            "TRANSCRIBING",
        )
        self.assertEqual(
            RecordingOverlay._display_for_state("Text typed")[0],
            "TEXT TYPED",
        )
        self.assertEqual(
            RecordingOverlay._display_for_state("Copied to clipboard")[0],
            "COPIED TO CLIPBOARD",
        )

    def test_status_colors_are_distinct(self) -> None:
        recording = RecordingOverlay._display_for_state("Recording")[3]
        transcribing = RecordingOverlay._display_for_state("Transcribing")[3]
        pasted = RecordingOverlay._display_for_state("Text typed")[3]

        self.assertEqual(len({recording, transcribing, pasted}), 3)

    def test_scroll_names_the_folder_being_saved_to(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = SettingsStore(Path(directory) / "settings.json")
            overlay = RecordingOverlay(Path("unused.png"), settings=settings)
            self.assertEqual(overlay._brand_line(), "WORDWRIGHT")

            settings.add_history_folder(Path(directory) / "Meetings")
            self.assertEqual(overlay._brand_line(), "WORDWRIGHT · SAVING TO MEETINGS")

            settings.add_history_folder(Path(directory) / "Quarterly planning notes")
            self.assertEqual(overlay._brand_line(), "WORDWRIGHT · SAVING TO QUARTERLY PLA…")

    def test_unknown_state_falls_back_to_ready(self) -> None:
        self.assertEqual(RecordingOverlay._display_for_state("Paste sent")[0], "READY")

    def test_scroll_menu_requires_an_explicit_action(self) -> None:
        self.assertIsNone(RecordingOverlay._menu_action_at(228, 10))
        self.assertIsNone(RecordingOverlay._menu_action_at(160, 38))
        self.assertEqual(RecordingOverlay._menu_action_at(250, 38), "record")
        self.assertEqual(RecordingOverlay._menu_action_at(370, 38), "open")

    def test_click_away_uses_only_the_visible_scroll_bounds(self) -> None:
        overlay = RecordingOverlay(
            Path("unused.png"),
            canvas_width=456,
            canvas_height=76,
        )

        self.assertTrue(overlay._point_in_scroll(120, 130, 100, 100))
        self.assertFalse(overlay._point_in_scroll(120, 180, 100, 100))
        self.assertFalse(overlay._point_in_scroll(560, 130, 100, 100))

    def test_positions_overlay_inside_selected_work_area(self) -> None:
        overlay = RecordingOverlay(
            Path("unused.png"),
            canvas_width=100,
            canvas_height=60,
        )
        work_area = (100, 200, 1100, 900)

        self.assertEqual(
            overlay._position_for_work_area(work_area, "top_center"),
            (550, 208),
        )
        self.assertEqual(
            overlay._position_for_work_area(work_area, "bottom_center"),
            (550, 832),
        )
        self.assertEqual(
            overlay._position_for_work_area(work_area, "left_center"),
            (108, 520),
        )
        self.assertEqual(
            overlay._position_for_work_area(work_area, "right_center"),
            (992, 520),
        )


if __name__ == "__main__":
    unittest.main()
