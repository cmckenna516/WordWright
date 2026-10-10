from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wordwright.settings import SettingsStore, folder_labels, parse_vocabulary


class SettingsStoreTests(unittest.TestCase):
    def test_privacy_sensitive_features_default_to_off(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            settings = store.snapshot()

        self.assertIsNone(settings.history_folder)
        self.assertEqual(settings.history_folders, ())
        self.assertEqual(settings.vocabulary, ())
        self.assertEqual(settings.model_choice, "auto")

    def test_updates_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            SettingsStore(path).update(
                show_overlay_always=False,
                overlay_position="bottom_center",
                model_choice="base.en",
                vocabulary=["Trace3", "Glean"],
            )
            settings = SettingsStore(path).snapshot()

        self.assertFalse(settings.show_overlay_always)
        self.assertEqual(settings.overlay_position, "bottom_center")
        self.assertEqual(settings.model_choice, "base.en")
        self.assertEqual(settings.vocabulary, ("Trace3", "Glean"))

    def test_saving_requires_an_added_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            with self.assertRaises(ValueError):
                store.update(history_folder=directory)
            with self.assertRaises(ValueError):
                store.set_history_destination(directory)

    def test_shortcut_is_validated_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = SettingsStore(path)
            self.assertEqual(store.snapshot().hotkey, "ctrl+alt+space")
            with self.assertRaises(ValueError):
                store.update(hotkey="space")
            store.update(hotkey="ctrl+shift+d")
            self.assertEqual(SettingsStore(path).snapshot().hotkey, "ctrl+shift+d")

    def test_rejects_unknown_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            with self.assertRaises(ValueError):
                store.update(model_choice="gigantic")

    def test_rejects_overlong_vocabulary_terms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            with self.assertRaises(ValueError):
                store.update(vocabulary=["x" * 61])

    def test_one_bad_value_does_not_reset_other_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "overlay_position": "bottom_center",
                        "model_choice": "no-such-model",
                        "vocabulary": ["Wordwright"],
                        "mind_map_enabled": False,
                    }
                ),
                encoding="utf-8",
            )
            settings = SettingsStore(path).snapshot()

        self.assertEqual(settings.overlay_position, "bottom_center")
        self.assertEqual(settings.model_choice, "auto")
        self.assertEqual(settings.vocabulary, ("Wordwright",))

    def test_multiple_folders_and_switching_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = SettingsStore(path)
            projects = str(Path(directory) / "Project X")
            meetings = str(Path(directory) / "Meetings")
            store.add_history_folder(projects)
            store.add_history_folder(meetings)
            store.add_history_folder(projects + "/")  # Same folder: not added twice.
            self.assertEqual(store.snapshot().history_folders, (projects, meetings))
            self.assertEqual(store.snapshot().history_folder, projects)

            store.set_history_destination(meetings)
            reloaded = SettingsStore(path).snapshot()
            self.assertEqual(reloaded.history_folder, meetings)

            store.set_history_destination(None)
            self.assertIsNone(store.snapshot().history_folder)
            self.assertEqual(len(store.snapshot().history_folders), 2)

    def test_removing_the_active_folder_stops_saving(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            store.add_history_folder(directory)
            store.remove_history_folder(directory)

            self.assertIsNone(store.snapshot().history_folder)
            self.assertEqual(store.snapshot().history_folders, ())
            self.assertTrue(Path(directory).is_dir())

    def test_test_build_settings_are_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for enabled, expected in ((True, directory), (False, None)):
                path = Path(directory) / f"settings-{enabled}.json"
                path.write_text(
                    json.dumps({"history_enabled": enabled, "history_folder": directory}),
                    encoding="utf-8",
                )
                settings = SettingsStore(path).snapshot()
                self.assertEqual(settings.history_folders, (directory,))
                self.assertEqual(settings.history_folder, expected)


class FolderLabelTests(unittest.TestCase):
    def test_duplicate_names_show_their_parent(self) -> None:
        labels = folder_labels(("C:/Work/Notes", "D:/Personal/Notes", "C:/Work/Meetings"))

        self.assertEqual(labels["C:/Work/Meetings"], "Meetings")
        self.assertIn("Work", labels["C:/Work/Notes"])
        self.assertNotEqual(labels["C:/Work/Notes"], labels["D:/Personal/Notes"])


class VocabularyParsingTests(unittest.TestCase):
    def test_splits_lines_and_commas_and_drops_duplicates(self) -> None:
        self.assertEqual(
            parse_vocabulary("Trace3\nGlean, n8n\n\n  trace3 \nCopilot  Studio"),
            ("Trace3", "Glean", "n8n", "Copilot Studio"),
        )


if __name__ == "__main__":
    unittest.main()
