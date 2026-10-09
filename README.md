# Wordwright

Wordwright is a local, hands-free dictation tool for Windows. Press
`Ctrl+Alt+Space`, speak, return to the destination text field, and press the
hotkey again. The completed English transcript is placed on the clipboard and
pasted at the cursor.

The app has a lightweight, old-school dark launcher plus a persistent,
focus-safe scroll overlay. Closing the launcher collapses the overlay to a tiny
closed scroll. Selecting that scroll opens two explicit choices: **Start
recording** or **Open app**. Selecting the scroll itself never starts recording.

## About this project

Wordwright is a personal project. I built it because the built-in Windows
dictation kept misspelling names and technical terms, and I wanted something
free, unlimited, and private that I control. I'm not a professional software
engineer: it was built with OpenAI Codex and reviewed with Claude, and it has
been tested on my own Windows machines.

You're welcome to install it, fork it, or use it as inspiration for building
your own tools.

## Status and disclaimer

- **Provided as is.** Wordwright is released under the [MIT License](LICENSE),
  without warranty of any kind. Use it at your own risk.
- **No support.** I don't offer user support, bug-fix commitments, or a
  roadmap. Issues and pull requests may not get a response.
- **Not a commercial product.** Wordwright is not affiliated with, endorsed by,
  or a replacement for any other dictation or transcription product, Microsoft
  Windows dictation, or OpenAI.
- **Unsigned builds.** Installers are not code-signed, so Windows will show an
  "Unknown publisher" warning.
- **Work devices.** Wordwright listens for a global hotkey, reads the
  microphone, and writes to the clipboard. Don't install it on an employer- or
  school-managed computer without approval from that organization's IT team.

## Install and open the Windows app

1. Download `Wordwright-Setup-0.1.0.exe` from this repository's
   [Releases](../../releases) page. If no release is listed yet, use the
   source steps below or build the installer yourself
   (see [Windows packaging](docs/windows-packaging.md)).
2. Double-click the installer. The current test build is not code-signed, so
   Windows may identify the publisher as **Unknown** even though the Installed
   Apps entry says **Charlie McKenna**. Only continue when the installer came
   from this repository and its published SHA-256 checksum matches.
3. Keep **Launch Wordwright** checked and select **Finish**.
4. Wait while the launcher says **Loading model**. The first launch downloads
   the local English speech model and requires an internet connection; later
   launches use the local copy.
5. When the launcher says **Ready to write**, Wordwright is ready. Press
   `Ctrl+Alt+Space` to start and stop dictation.

After that, open **Wordwright** from the Windows Start menu like any other
app. You can also right-click its taskbar icon while it is open and pin it.
Closing the launcher window hides it; choose **Quit Wordwright** in the
launcher or tray menu to stop the app completely.

## Running directly from the source folder

These steps are for contributors and source ZIP testers. Normal installed users
do not need Python or the setup scripts.

### The first time you use Wordwright

1. After downloading `WordWright-main.zip`, right-click the ZIP and choose
   **Extract All**. Do not double-click setup while viewing files inside the ZIP.
2. Open the newly extracted `WordWright-main` folder in File Explorer.
3. Double-click **Setup Wordwright.cmd**.
4. If Windows asks for permission, allow the script to run.
5. Keep the setup window open while dependencies and the local speech model
   install. This can take several minutes and requires an internet connection.
6. Setup briefly opens the default microphone and verifies real speech
   recognition, the clipboard, and the global hotkey hook. It does not retain
   the microphone samples or the verification transcript.
7. Wait until the window says **Wordwright setup and functional checks are
   complete**. You only need to do this once.
8. Double-click **Start Wordwright.cmd**.
9. Wait until Wordwright says **Idle** or shows the **Ready** notification.

Setup automatically looks for a compatible Python already available on the
computer. If it reports that Python cannot be found, install Python 3.11 or
3.12 and select **Add Python to PATH** during its installer, then run
**Setup Wordwright.cmd** again.

### If the launcher does not appear

1. Run **Setup Wordwright.cmd** again and do not close it until it says
   **Wordwright setup and functional checks are complete**. Any other ending
   means setup failed; the displayed check identifies the failing subsystem.
2. Run **Start Wordwright.cmd** again. It now opens visibly and checks that
   Wordwright stays running instead of failing silently.
3. If the start window remains open with an error, copy that error when asking
   for help. The same diagnostic details are stored in
   `%LOCALAPPDATA%\Wordwright\logs\wordwright.log`.

The first successful start may briefly show **Loading model**, but setup now
downloads and tests the model in advance. Do not press the recording hotkey
until the launcher status changes to **Idle**.

### Dictate text

1. Click the text box where you want the words to appear.
2. Press `Ctrl+Alt+Space` once. The overlay turns red when recording begins.
3. Speak normally. You can take your hands off the keyboard.
4. Return to the destination text box and leave the cursor there.
5. Press `Ctrl+Alt+Space` again to stop recording.
6. Wait while the overlay turns blue. The completed text is pasted at the
   cursor and remains on the clipboard as a backup.

Wordwright never presses Enter or sends the surrounding message or form.

### Open the launcher again

Clicking the launcher window's **X** hides the window but keeps Wordwright
running. The hotkey and overlay continue to work.

To reopen the launcher:

1. Select the closed scroll at the top center of the desktop and choose **Open
   app**, or find the Wordwright icon in the Windows system tray near the clock.
2. If it is hidden, click the **^** arrow first.
3. Right-click the Wordwright icon and choose **Open Wordwright**.

The packaged release is the recommended path for ordinary use. These scripts
remain available for development and troubleshooting.

## Packaged Windows application

The packaging project builds a normal per-user Windows installer containing its
own Python runtime and dependencies. Installed users launch Wordwright from
the Start menu or a pinned taskbar icon; they do not need Python or the
repository setup scripts.

The initial unsigned test installer uses `Charlie McKenna` as descriptive
publisher metadata. Windows trust warnings require code signing and are not
removed by changing that text or inventing a company name. See
[Windows packaging and publisher identity](docs/windows-packaging.md) for the
build, installation, upgrade, and future signing approach.

### Completely close Wordwright

Use either of these methods:

- Click **Quit Wordwright** at the bottom of the launcher; or
- Right-click the Wordwright tray icon and choose **Quit Wordwright**.

The overlay disappears and the hotkey stops working when the program has fully
closed. Clicking the window's **X** does not fully close it. To start the app
again after quitting, double-click **Start Wordwright.cmd**.

This repository currently contains the first testable prototype. It captures
microphone audio only; it does not capture system audio, save transcripts,
rewrite text, or submit forms.

## Detailed first-test behavior

1. Start Wordwright and wait for the **Ready** notification. The first launch
   downloads the local `small.en` speech model and can take several minutes.
2. Focus a text field and press `Ctrl+Alt+Space`.
3. Confirm that the permanent top-center scroll unfurls in red and says
   **RECORDING**, then speak hands-free.
4. You may navigate while recording. Return to the desired text field before
   stopping.
5. Press `Ctrl+Alt+Space` again and leave that field focused.
6. The scroll turns blue and says **TRANSCRIBING**. Wordwright sends paste to
   the focused control in classic Windows apps, browsers, Electron apps, Office,
   and other custom text surfaces. It then says **PASTE SENT** in green,
   or **COPIED TO CLIPBOARD** in amber when Wordwright itself or an obvious
   Windows shell surface has focus. The transcript remains on the clipboard in
   both cases.

Wordwright never presses Enter or deliberately submits the surrounding form.

## Tray states

- Yellow badge: loading the local model
- Closed scroll: idle and ready; select it for Start recording or Open app
- Red expanded scroll: recording
- Blue expanded scroll: transcribing
- Green expanded scroll: paste command sent
- Amber expanded scroll: copied to clipboard because no text field was found
- Purple badge: error

Right-click the tray icon and choose **Quit Wordwright** to exit.

The tray menu can also reopen the launcher and turn off the always-visible idle
overlay. Active recording, transcription, success, and error states remain
visible even when the idle overlay is disabled.

## Launcher and settings

The initial launcher provides:

- Current model, microphone, hotkey, and recording state
- Overlay visibility and top/bottom/left/right positioning
- Optional user-selected WAV cues for recording start and stop
- A privacy-safe History placeholder; transcript history is not implemented or
  enabled in this build

Settings are stored locally under `%LOCALAPPDATA%\Wordwright`. Diagnostic logs
are written there as rotating text files and do not include transcript bodies.

## Developer setup

Python 3.11 or 3.12 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

List microphone inputs:

```powershell
.\.venv\Scripts\python.exe -m wordwright --list-microphones
```

Run with diagnostic logging:

```powershell
.\scripts\run-debug.ps1
```

Run without a console window:

```powershell
.\scripts\run.ps1
```

The default is CPU inference using the quantized `small.en` model. This keeps
the first test independent of CUDA runtime setup. GPU inference and larger
models will be benchmarked only after the interaction loop is validated.

## Automated tests

GitHub Actions runs the unit suite and builds the packaged Windows application
for every pull request into `main`. To run the same unit suite locally:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Privacy

Audio is held in memory and is not intentionally retained. Transcript text is
not logged or sent to an API. A network connection is needed to install Python
dependencies and download the speech model for the first time.

## Third-party software

Wordwright depends on open-source libraries and downloads an open-source speech
model on first launch. Their licenses are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Current limitations

- English only
- Windows only
- Paste is best-effort; Windows does not provide a universal way to confirm
  that every application accepted it
- Windows may block simulated paste into an elevated application unless
  Wordwright is running at the same privilege level
- The destination must remain focused while transcription finishes
- The top-center overlay is deliberately always visible while the app runs
- No automatic updater, transcript archive, correction learning, or
  hold-to-talk mode yet
- Some microphones may not accept the prototype's 16 kHz capture format

See [the product specification](docs/product-spec.md) and
[technical plan](docs/technical-plan.md) for the original prototype scope. See
[the product direction and roadmap](docs/design-and-roadmap.md) for the launcher,
privacy, originality, correction-learning, mind-map, statistics, and export
plans.
Use the [dictation accuracy test script](docs/test-script.md) for repeatable
model and release comparisons.
