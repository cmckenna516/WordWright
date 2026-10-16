# Windows packaging and publisher identity

The distributable application is a 64-bit, per-user Windows installation. It
contains its own Python runtime and dependencies, creates a Start menu shortcut,
offers an optional desktop shortcut, appears in Installed Apps, and can be
pinned to the taskbar. Users do not run the repository setup scripts or install
Python.

The Settings page can optionally register the installed executable under the
current user's Windows `Run` key. The option is off by default, uses the
`--startup` argument to keep the launcher hidden, and does not require
administrator permission. Uninstall removes Wordwright's named startup value.

## Publisher

The initial installer metadata uses `Charlie McKenna`. A company is not needed
to publish a personal utility, and the value can be overridden during a build:

```powershell
.\packaging\build-windows.ps1 -Publisher "Different Publisher"
```

This metadata appears in Installed Apps and file properties. It does not make
an unsigned executable a trusted Windows publisher. Windows SmartScreen and the
download warning rely on a valid code-signing certificate and reputation.
Do not create a company name merely to fill this field.

Before wider public distribution, choose one of these signing paths:

1. Sign personally using a certificate issued to the individual publisher.
2. Form an entity and sign future releases using a certificate issued to it.
3. Continue distributing unsigned test builds while clearly documenting the
   expected warning and publishing checksums from the official repository.

Signing and product naming are separate decisions. Changing the display name or
publisher later does not require changing the local privacy architecture.

Before public distribution, choose the long-term publisher identity and obtain
a matching Windows code-signing certificate. The certificate—not merely the
installer's Publisher text—is what replaces the `Unknown publisher` warning.

## Release validation record

Wordwright v0.3.0 was validated from the published installer on October 16,
2026. The installed app launched normally with the full launcher, registered
per-user sign-in startup, returned after sign-in with only the compact overlay,
and completed press-and-hold recording, release, transcription, and text entry.

## Build

Install Inno Setup 6, then run:

```powershell
.\packaging\build-windows.ps1
```

Outputs:

- `dist\Wordwright\Wordwright.exe`: unpacked application build
- `release\Wordwright-Setup-0.3.0.exe`: installer for testers

The installer is per-user and does not require elevation. The speech model,
settings, and diagnostic logs remain under `%LOCALAPPDATA%\Wordwright`, so an
application upgrade or uninstall does not silently delete personal settings.

## Release verification

Before publishing a build:

1. Run the automated tests.
2. Launch `dist\Wordwright\Wordwright.exe` and confirm the model reaches
   the ready state.
3. Install the generated setup executable as the current user.
4. Confirm the Start menu shortcut, overlay, hotkey, microphone capture,
   transcription, clipboard fallback, and clean shutdown.
5. Enable sign-in startup, run the registered command, and confirm only the
   compact scroll appears. Launch the shortcut again and confirm the existing
   full window opens.
6. Disable sign-in startup and confirm the registration is removed.
7. Uninstall it and confirm the startup registration is removed while
   `%LOCALAPPDATA%\Wordwright` remains intact.
8. Publish the setup file's SHA-256 checksum beside the download.

The log at `%LOCALAPPDATA%\Wordwright\logs\wordwright.log` records model
startup and errors but never transcript bodies.

## Publishing a GitHub release

The `Windows Release` workflow builds and publishes the installer when a
version tag is pushed. Before tagging, update the matching version in
`pyproject.toml`, `src/wordwright/__init__.py`, and the packaging defaults, then
merge the tested change into `main`.

```powershell
git tag v0.3.0
git push origin v0.3.0
```

The workflow runs the unit tests, builds `Wordwright-Setup-0.3.0.exe`, creates
its SHA-256 checksum, and attaches both files to a GitHub Release. Testers
should download the `.exe` from the latest Release and should not download
GitHub's automatically generated source-code archives.

## From-scratch build and startup test

The startup control is intentionally unavailable when Wordwright is run from
source. Build and install the packaged application before testing it.

### 1. Install the build tools

Install these once on the Windows computer that will build Wordwright:

- 64-bit Python 3.11 or 3.12. Confirm that `python --version` reports the real
  interpreter rather than opening the Microsoft Store.
- Inno Setup 6. The build script looks for its compiler in the standard install
  locations.
- Git, if the repository has not already been downloaded.

Close and reopen PowerShell after installing the tools, then check them:

```powershell
python --version
git --version
```

### 2. Get a clean working copy

For a new checkout:

```powershell
git clone https://github.com/cmckenna516/WordWright.git
Set-Location WordWright
```

When testing changes that have not been pushed yet, use the existing working
copy containing those changes instead of cloning the public repository.

### 3. Build the installer

From the repository root:

```powershell
$pythonPath = (Get-Command python.exe).Source
.\packaging\build-windows.ps1 -Python $pythonPath
```

If `Get-Command` points to a non-working Windows Store alias, replace
`$pythonPath` with the full path to the installed Python 3.11 or 3.12
`python.exe`.

The first build creates `.packaging-venv`, downloads the project dependencies,
and can take several minutes. A successful build produces:

```text
release\Wordwright-Setup-0.3.0.exe
```

### 4. Install and verify the default

1. Quit any running Wordwright instance from its tray menu.
2. Uninstall an older Wordwright build from **Settings → Apps → Installed
   apps** if one is present.
3. Run `release\Wordwright-Setup-0.3.0.exe`. The unsigned test build may show
   the documented Unknown publisher warning.
4. Let the installer launch Wordwright.
5. Open **Settings → Windows**.

Expected result: **Start Wordwright when I sign in to Windows** is off and can
be changed. If it says the option is available only in the installed app, the
source launcher was opened instead of the installed executable.

### 5. Test automatic compact startup

1. Enable **Start Wordwright when I sign in to Windows**.
2. Close the full launcher window. Confirm Wordwright continues running in the
   tray and the compact scroll remains available.
3. Quit Wordwright from the tray menu so the next launch definitely comes from
   Windows.
4. Restart the computer, or sign out and sign back in.
5. Wait for Windows to finish loading startup applications.

Expected results:

- The full Wordwright launcher does not appear.
- Only the compact scroll and tray icon appear.
- Hovering over the tray icon eventually reports **Wordwright — Idle**, which
  means the model and hotkeys are ready.
- Dictation works from Notepad without first opening the full launcher.

Windows may delay ordinary sign-in applications briefly while the desktop is
settling, so the scroll is not guaranteed to appear at the first instant the
desktop becomes visible.

### 6. Test an ordinary launch while it is already running

With Wordwright still running from sign-in, open it from the Start menu or its
desktop shortcut.

Expected results:

- The existing full launcher opens and receives focus.
- No “already running” message appears.
- No second tray icon, scroll, hotkey listener, or transcription process is
  created.

### 7. Test disabling startup

1. In the full launcher, turn the startup setting off.
2. Quit Wordwright from its tray menu.
3. Sign out and sign back in.

Expected result: Wordwright does not start automatically. Opening it manually
still displays the full launcher normally.

### 8. Test uninstall cleanup

1. Enable the startup setting again, then quit Wordwright.
2. Uninstall Wordwright from **Settings → Apps → Installed apps**.
3. Sign out and sign back in.

Expected result: Windows does not try to start Wordwright. The installer leaves
`%LOCALAPPDATA%\Wordwright` in place intentionally so models and ordinary user
settings are not silently deleted.

