from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from wordwright.__main__ import main, parse_args
from wordwright.startup import RUN_KEY, VALUE_NAME, StartupRegistration


class FakeRegistry:
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str], tuple[str, int]] = {}
        self.closed = 0

    def OpenKey(self, root, subkey, reserved, access):
        del reserved, access
        if not any(key[:2] == (root, subkey) for key in self.values):
            raise FileNotFoundError
        return root, subkey

    def CreateKeyEx(self, root, subkey, reserved, access):
        del reserved, access
        return root, subkey

    def QueryValueEx(self, key, name):
        try:
            return self.values[(*key, name)]
        except KeyError as exc:
            raise FileNotFoundError from exc

    def SetValueEx(self, key, name, reserved, value_type, value):
        del reserved
        self.values[(*key, name)] = value, value_type

    def DeleteValue(self, key, name):
        try:
            del self.values[(*key, name)]
        except KeyError as exc:
            raise FileNotFoundError from exc

    def CloseKey(self, key):
        del key
        self.closed += 1


class StartupRegistrationTests(unittest.TestCase):
    def test_startup_command_line_mode_is_explicit(self) -> None:
        self.assertTrue(parse_args(["--startup"]).startup)
        self.assertFalse(parse_args([]).startup)

    def make_registration(self, registry: FakeRegistry) -> StartupRegistration:
        return StartupRegistration(
            Path(r"C:\Program Files\Wordwright\Wordwright.exe"),
            packaged=True,
            windows=True,
            installed=True,
            registry=registry,
        )

    def test_is_off_by_default(self) -> None:
        registration = self.make_registration(FakeRegistry())

        self.assertFalse(registration.is_enabled())

    def test_enable_writes_quoted_per_user_command(self) -> None:
        registry = FakeRegistry()
        registration = self.make_registration(registry)

        registration.set_enabled(True)

        value, value_type = registry.values[("HKCU", RUN_KEY, VALUE_NAME)]
        self.assertEqual(
            value,
            r'"C:\Program Files\Wordwright\Wordwright.exe" --startup',
        )
        self.assertEqual(value_type, registry.REG_SZ)
        self.assertTrue(registration.is_enabled())

    def test_disable_removes_only_wordwright_value(self) -> None:
        registry = FakeRegistry()
        registration = self.make_registration(registry)
        registration.set_enabled(True)
        registry.values[("HKCU", RUN_KEY, "Another app")] = (
            "other.exe",
            registry.REG_SZ,
        )

        registration.set_enabled(False)

        self.assertNotIn(("HKCU", RUN_KEY, VALUE_NAME), registry.values)
        self.assertIn(("HKCU", RUN_KEY, "Another app"), registry.values)

    def test_stale_command_is_not_reported_as_enabled(self) -> None:
        registry = FakeRegistry()
        registry.values[("HKCU", RUN_KEY, VALUE_NAME)] = (
            "old-location.exe --startup",
            registry.REG_SZ,
        )
        registration = self.make_registration(registry)

        self.assertFalse(registration.is_enabled())

    def test_source_run_is_unavailable(self) -> None:
        registration = StartupRegistration(
            packaged=False,
            windows=True,
            registry=FakeRegistry(),
        )

        self.assertFalse(registration.available)
        with self.assertRaisesRegex(RuntimeError, "installed Windows app"):
            registration.set_enabled(True)

    def test_unpackaged_test_build_is_not_treated_as_installed(self) -> None:
        registration = StartupRegistration(
            packaged=True,
            windows=True,
            installed=False,
            registry=FakeRegistry(),
        )

        self.assertFalse(registration.available)


class StartupLaunchTests(unittest.TestCase):
    @patch("wordwright.__main__.show_already_running_message")
    @patch("wordwright.__main__.SingleInstance.request_show", return_value=True)
    @patch("wordwright.__main__.SingleInstance.acquire", return_value=None)
    @patch("wordwright.__main__.configure_logging")
    def test_normal_second_launch_opens_existing_window(
        self,
        configure_logging,
        acquire,
        request_show,
        show_message,
    ) -> None:
        self.assertEqual(main([]), 0)

        request_show.assert_called_once_with()
        show_message.assert_not_called()

    @patch("wordwright.__main__.show_already_running_message")
    @patch("wordwright.__main__.SingleInstance.request_show")
    @patch("wordwright.__main__.SingleInstance.acquire", return_value=None)
    @patch("wordwright.__main__.configure_logging")
    def test_duplicate_startup_launch_exits_quietly(
        self,
        configure_logging,
        acquire,
        request_show,
        show_message,
    ) -> None:
        self.assertEqual(main(["--startup"]), 0)

        request_show.assert_not_called()
        show_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
