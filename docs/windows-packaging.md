# Windows packaging and publisher identity

The distributable application is a 64-bit, per-user Windows installation. It
contains its own Python runtime and dependencies, creates a Start menu shortcut,
offers an optional desktop shortcut, appears in Installed Apps, and can be
pinned to the taskbar. Users do not run the repository setup scripts or install
Python.

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

## Build

Install Inno Setup 6, then run:

```powershell
.\packaging\build-windows.ps1
```

Outputs:

- `dist\Wordwright\Wordwright.exe`: unpacked application build
- `release\Wordwright-Setup-0.1.0.exe`: installer for testers

The installer is per-user and does not require elevation. The speech model,
settings, and diagnostic logs remain under `%LOCALAPPDATA%\Wordwright`, so an
application upgrade or uninstall does not silently delete personal settings or
future opt-in history.

## Release verification

Before publishing a build:

1. Run the automated tests.
2. Launch `dist\Wordwright\Wordwright.exe` and confirm the model reaches
   the ready state.
3. Install the generated setup executable as the current user.
4. Confirm the Start menu shortcut, overlay, hotkey, microphone capture,
   transcription, clipboard fallback, and clean shutdown.
5. Uninstall it and confirm `%LOCALAPPDATA%\Wordwright` remains intact.
6. Publish the setup file's SHA-256 checksum beside the download.

The log at `%LOCALAPPDATA%\Wordwright\logs\wordwright.log` records model
startup and errors but never transcript bodies.

