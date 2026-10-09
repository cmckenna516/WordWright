from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wordwright.settings import SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def test_privacy_sensitive_features_default_to_off(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            settings = store.snapshot()

        self.assertFalse(settings.history_enabled)
        self.assertFalse(settings.correction_learning_enabled)
        self.assertFalse(settings.mind_map_enabled)

    def test_updates_are_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            SettingsStore(path).update(
                show_overlay_always=False,
                overlay_position="bottom_center",
            )
            settings = SettingsStore(path).snapshot()

        self.assertFalse(settings.show_overlay_always)
        self.assertEqual(settings.overlay_position, "bottom_center")

    def test_history_requires_an_explicit_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            with self.assertRaises(ValueError):
                store.update(history_enabled=True)

    def test_learning_requires_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            with self.assertRaises(ValueError):
                store.update(correction_learning_enabled=True)


if __name__ == "__main__":
    unittest.main()

