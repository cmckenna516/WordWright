from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wordwright.settings import SettingsStore, parse_vocabulary


class SettingsStoreTests(unittest.TestCase):
    def test_privacy_sensitive_features_default_to_off(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            settings = store.snapshot()

        self.assertFalse(settings.history_enabled)
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

    def test_history_requires_an_explicit_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            with self.assertRaises(ValueError):
                store.update(history_enabled=True)

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

    def test_history_with_folder_survives_reload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            SettingsStore(path).update(history_folder=directory, history_enabled=True)
            settings = SettingsStore(path).snapshot()

        self.assertTrue(settings.history_enabled)


class VocabularyParsingTests(unittest.TestCase):
    def test_splits_lines_and_commas_and_drops_duplicates(self) -> None:
        self.assertEqual(
            parse_vocabulary("Trace3\nGlean, n8n\n\n  trace3 \nCopilot  Studio"),
            ("Trace3", "Glean", "n8n", "Copilot Studio"),
        )


if __name__ == "__main__":
    unittest.main()
