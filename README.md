# Wordwright

Local dictation for Windows. Hold `Ctrl+Alt` while you speak and release to
transcribe, or press `Ctrl+Shift+Space` once to start and again to stop. The
text is typed where your cursor is, and speech recognition runs entirely on
your PC.

<!-- TODO: add docs/media/demo.gif here: one 10-second dictation into a text box. -->

- **Private.** Audio stays in memory and is discarded. Transcripts are never
  logged, saved, or sent anywhere.
- **Learns your words.** Add names, products, and jargon on the **Speech** page
  so they're spelled your way.
- **Fits your PC.** Wordwright picks a speech model for your hardware: the most
  accurate one on PCs with an NVIDIA GPU, a lighter one on laptops and ARM PCs.
- **Stays out of the way.** A small scroll at the top of the screen shows when
  it's listening; it never takes focus from the app you're typing in.

## Quickstart

1. Download `Wordwright-Setup-x.y.z.exe` from the
   [latest Wordwright release](../../releases/latest) and run it. Do not use
   GitHub's **Source code** ZIP files; those are for development. The installer isn't code-signed, so
   Windows shows an "Unknown publisher" warning.
2. Wait for **Ready to write**. The first launch downloads the speech model and
   needs an internet connection; after that it works offline.
3. Click into any text box, hold `Ctrl+Alt` while you speak, then release.
   For hands-free dictation, press `Ctrl+Shift+Space`, speak, then press it again.

Press `Esc` while recording to cancel without typing anything.

## Using it

| You want to | Do this |
| --- | --- |
| Hold to dictate | Hold `Ctrl+Alt`, speak, then release to transcribe |
| Toggle hands-free dictation | Press `Ctrl+Shift+Space` once to start and again to stop |
| Change either shortcut | **Settings** page → **Shortcuts** → pick keys → **Apply** |
| Start Wordwright with Windows | **Settings** page → **Windows** → enable **Start Wordwright when I sign in** |
| Cancel a recording | `Esc` (Wordwright only listens for Esc while recording) |
| Teach it your words | **Speech** page → one word or phrase per line → **Save words** |
| Change the speech model | **Speech** page → **Model** (Automatic is the default) |
| Move or hide the overlay | **Settings** page, or the tray icon menu |
| Quit completely | **Quit Wordwright** in the app or tray menu (closing the window only hides it) |

If no text field has focus when transcription finishes, the text is copied to
the clipboard instead so the dictation isn't lost. Wordwright never presses
Enter, so it can't submit a form or send a message for you.

When sign-in startup is enabled, the installed app launches with only the
compact scroll visible. Opening Wordwright from its shortcut still opens the
full window, even when it is already running.

### Speech models

| Your PC | Model chosen automatically |
| --- | --- |
| NVIDIA GPU with CUDA 12 cuBLAS and cuDNN 9 installed | `large-v3-turbo` on the GPU |
| 8+ CPU threads and 12 GB+ RAM | `small.en` on the CPU |
| ARM64 (Snapdragon) or lighter CPU | `base.en` on the CPU |

On ARM64 PCs the speech engine runs under x64 emulation because it has no
native ARM64 Windows build yet. If you'd rather trade speed for accuracy,
choose `small.en` on the Speech page.

## Limitations

- English only, Windows only.
- Windows blocks typing into apps running as administrator unless Wordwright
  also runs as administrator; the text goes to the clipboard instead.
- Keep the destination field focused until the text appears.

## About this project

Wordwright is a personal project. I built it because the built-in Windows
dictation kept misspelling names and technical terms, and I wanted something
free, unlimited, and private that I control. I'm not a professional software
engineer: it was built with OpenAI Codex and reviewed with Claude, and it's
been tested on my own Windows machines. You're welcome to install it, fork it,
or use it as inspiration for your own tools.

- **Provided as is**, under the [MIT License](LICENSE), without warranty.
- **No support.** Issues and pull requests may not get a response.
- **Not affiliated** with any other dictation product, Microsoft, or OpenAI.
- **Work devices.** Wordwright listens for a global hotkey, reads the
  microphone, and types into other apps. Don't install it on an employer- or
  school-managed computer without approval from that organization's IT team.

## More

- [Running from source, tests, and troubleshooting](docs/development.md)
- [Windows packaging](docs/windows-packaging.md)
- [Design and roadmap](docs/design-and-roadmap.md)
- [Dictation accuracy test script](docs/test-script.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
