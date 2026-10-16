from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - winreg exists on Windows only.
    winreg = None  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_PATH_KEY = r"Software\Microsoft\Windows\CurrentVersion\App Paths\Wordwright.exe"
VALUE_NAME = "Wordwright"
STARTUP_ARGUMENT = "--startup"


class StartupRegistration:
    """Manage Wordwright's per-user Windows sign-in registration."""

    def __init__(
        self,
        executable: Path | str | None = None,
        *,
        packaged: bool | None = None,
        windows: bool | None = None,
        installed: bool | None = None,
        registry: Any | None = None,
    ) -> None:
        self._executable = Path(executable or sys.executable)
        self._packaged = (
            bool(getattr(sys, "frozen", False)) if packaged is None else packaged
        )
        self._windows = os.name == "nt" if windows is None else windows
        self._installed = installed
        self._registry = winreg if registry is None else registry

    @property
    def available(self) -> bool:
        """Return whether this is an installed Windows build."""

        return (
            self._windows
            and self._packaged
            and self._registry is not None
            and self._is_installed()
        )

    def _is_installed(self) -> bool:
        if self._installed is not None:
            return self._installed
        registry = self._registry
        try:
            key = registry.OpenKey(
                registry.HKEY_CURRENT_USER,
                APP_PATH_KEY,
                0,
                registry.KEY_READ,
            )
            try:
                value, value_type = registry.QueryValueEx(key, "")
            finally:
                registry.CloseKey(key)
        except (FileNotFoundError, OSError):
            return False
        return (
            value_type == registry.REG_SZ
            and os.path.normcase(os.path.abspath(str(value)))
            == os.path.normcase(os.path.abspath(str(self._executable)))
        )

    @property
    def command(self) -> str:
        """Return the safely quoted command stored in the Windows Run key."""

        return subprocess.list2cmdline((str(self._executable), STARTUP_ARGUMENT))

    def is_enabled(self) -> bool:
        if not self.available:
            return False
        registry = self._registry
        try:
            key = registry.OpenKey(registry.HKEY_CURRENT_USER, RUN_KEY, 0, registry.KEY_READ)
            try:
                value, value_type = registry.QueryValueEx(key, VALUE_NAME)
            finally:
                registry.CloseKey(key)
        except FileNotFoundError:
            return False
        except OSError:
            LOGGER.exception("Unable to read the Windows startup registration")
            return False
        return (
            value_type == registry.REG_SZ
            and str(value).casefold() == self.command.casefold()
        )

    def set_enabled(self, enabled: bool) -> None:
        if not self.available:
            raise RuntimeError("Startup is available only in the installed Windows app.")
        registry = self._registry
        if enabled:
            key = registry.CreateKeyEx(
                registry.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                registry.KEY_SET_VALUE,
            )
            try:
                registry.SetValueEx(key, VALUE_NAME, 0, registry.REG_SZ, self.command)
            finally:
                registry.CloseKey(key)
            return

        try:
            key = registry.OpenKey(
                registry.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                registry.KEY_SET_VALUE,
            )
        except FileNotFoundError:
            return
        try:
            try:
                registry.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
        finally:
            registry.CloseKey(key)
