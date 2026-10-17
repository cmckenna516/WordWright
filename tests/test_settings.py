from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wordwright.settings import SettingsStore, parse_vocabulary


class SettingsStoreTests(unittest.TestCase):
    def test_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            settings = store.snapshot()

        self.assertEqual(settings.vocabulary, ())
        self.assertEqual(settings.model_choice, "auto")
        self.assertEqual(settings.hotkey, "ctrl+shift+space")
        self.assertEqual(settings.hold_hotkey, "ctrl+alt")
        self.assertIsNone(settings.microphone_device)

    def test_updates_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            SettingsStore(path).update(
                show_overlay_always=False,
                overlay_position="bottom_center",
                model_choice="base.en",
                vocabulary=["Trace3", "Glean"],
                microphone_device="WASAPI::Headset Microphone",
            )
            settings = SettingsStore(path).snapshot()

        self.assertFalse(settings.show_overlay_always)
        self.assertEqual(settings.overlay_position, "bottom_center")
        self.assertEqual(settings.model_choice, "base.en")
        self.assertEqual(settings.vocabulary, ("Trace3", "Glean"))
        self.assertEqual(settings.microphone_device, "WASAPI::Headset Microphone")

    def test_rejects_blank_microphone_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            with self.assertRaises(ValueError):
                store.update(microphone_device="  ")

    def test_shortcut_is_validated_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = SettingsStore(path)
            self.assertEqual(store.snapshot().hotkey, "ctrl+shift+space")
            with self.assertRaises(ValueError):
                store.update(hotkey="space")
            store.update(hotkey="ctrl+shift+d")
            self.assertEqual(SettingsStore(path).snapshot().hotkey, "ctrl+shift+d")

    def test_hold_shortcut_is_validated_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = SettingsStore(path)
            with self.assertRaises(ValueError):
                store.update(hold_hotkey="alt")
            store.update(hold_hotkey="win+alt")
            self.assertEqual(SettingsStore(path).snapshot().hold_hotkey, "win+alt")

    def test_overlapping_shortcuts_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            with self.assertRaisesRegex(ValueError, "overlaps"):
                store.update(hotkey="ctrl+alt+space")

    def test_legacy_default_is_migrated_away_from_new_hold_chord(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"hotkey": "ctrl+alt+space"}), encoding="utf-8")
            settings = SettingsStore(path).snapshot()

        self.assertEqual(settings.hotkey, "ctrl+shift+space")
        self.assertEqual(settings.hold_hotkey, "ctrl+alt")

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

class VocabularyParsingTests(unittest.TestCase):
    def test_splits_lines_and_commas_and_drops_duplicates(self) -> None:
        self.assertEqual(
            parse_vocabulary("Trace3\nGlean, n8n\n\n  trace3 \nCopilot  Studio"),
            ("Trace3", "Glean", "n8n", "Copilot Studio"),
        )


if __name__ == "__main__":
    unittest.main()
