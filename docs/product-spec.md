# Product specification: version 0.1

## Summary

Wordwright is a Windows dictation utility for people who want accurate, unlimited speech-to-text without sending their recordings or transcripts to a hosted service.

Version 0.1 addresses one job:

> While working in a text field, I want to dictate a passage hands-free and have the completed transcript inserted at my cursor.

It is not a meeting recorder or note-taking product.

## Target user

The initial user is the developer running Wordwright on a personal Windows 11 desktop. Broader distribution is a later concern. Version 0.1 may assume a capable machine and a user comfortable running early-stage software.

Reference development hardware:

- Windows 11 Pro
- AMD Ryzen 9 5900X, 12 cores / 24 logical processors
- 32 GB RAM
- NVIDIA GeForce RTX 3070 Ti

## Primary workflow

1. The user focuses a text field.
2. The user presses `Ctrl+Alt+Space`.
3. Wordwright begins microphone capture and enters the **Recording** state.
4. The user speaks hands-free and may navigate or scroll elsewhere.
5. The user returns focus to the destination text field.
6. The user presses `Ctrl+Alt+Space` again.
7. Wordwright stops capture and enters the **Transcribing** state.
8. The user leaves the destination field focused.
9. Wordwright creates punctuated English text locally.
10. Wordwright places the result on the clipboard and pastes it at the cursor.
11. Wordwright returns to **Idle**.

The destination is the text field focused when recording is stopped. Version 0.1 does not remember or restore a cursor position captured when recording began.

## Application states

| State | Meaning | Required indication |
| --- | --- | --- |
| Idle | Ready for a new recording | Compact neutral scroll at the top center and neutral tray icon |
| Recording | Microphone audio is being captured | Top-center scroll expands and shows a red state badge |
| Transcribing | Recording has stopped and local inference is running | Top-center scroll remains expanded, pulses gently, and shows a blue state badge |
| Success | Text was sent to the focused field | Brief confirmation |
| Error | Recording, transcription, or insertion failed | Visible error notification |

The status interface must not steal focus from the destination text field. The scroll overlay remains visible while Wordwright runs, stays click-through, and contracts to a compact idle state.

## Functional requirements

### Hotkey

- Holding `Ctrl+Alt` starts recording and releasing either key stops recording
  and starts transcription.
- `Ctrl+Shift+Space` toggles recording.
- The first press starts recording.
- The second press stops recording and starts transcription.
- Toggle and hold shortcuts are independently configurable.
- Shortcuts that overlap the complete hold combination must be rejected.
- Repeated or accidental input must not launch overlapping transcription jobs.

### Audio capture

- Capture only the selected/default microphone.
- Do not capture speaker or system output.
- Stop cleanly if the microphone becomes unavailable.
- Audio should remain in memory where practical.
- Any temporary audio created by the implementation must be removed after the attempt completes.

### Transcription

- Run locally on the user's machine.
- Support English only.
- Produce mostly verbatim text with punctuation.
- Do not deliberately remove filler words, rewrite sentences, summarize, or invent content.
- Transcription may occur after recording stops; live transcription is not required.

### Text insertion

- Paste into the text field focused when the stop hotkey is pressed.
- Never press Enter, submit a form, click a button, or send a message.
- Leave the transcript on the clipboard so the user can recover it if automatic insertion fails.
- Leave the transcript on the clipboard so the user can paste it manually if the destination application does not accept the automatic paste.

### Storage

- Version 0.1 does not maintain a transcript archive.
- Version 0.1 does not retain recordings.
- Application configuration may be stored locally.
- Logs must not contain captured audio or complete transcript text by default.

## Privacy requirements

- No account is required.
- No telemetry is required.
- Audio and transcript text must not be sent to a transcription API.
- Once application dependencies and the speech model are installed, ordinary dictation should not require a network connection.
- The interface must make recording state obvious to reduce accidental capture.

## Acceptance criteria

Version 0.1 is successful when all of the following are true:

- Both toggle and hold shortcuts control microphone capture without the application being focused.
- Releasing the configured hold chord stops capture and starts transcription.
- The user can speak hands-free between the two hotkey presses.
- A visible state change occurs when recording starts and when transcription begins.
- A normal English paragraph is returned with usable punctuation.
- Automatic paste is verified manually in:
  - a standard browser text area,
  - a browser content-editable field,
  - Windows Notepad,
  - the Codex text composer.
- The transcript remains available on the clipboard.
- No automatic Enter key or form submission occurs.
- The same workflow functions with the computer disconnected from the network after setup.
- Audio is not retained after processing.

Accuracy and latency targets will be set after collecting representative recordings and benchmarking candidate models on the development computer.

## Explicitly deferred

- System-audio capture
- Meeting transcription
- Speaker diarization
- Transcript history and search
- Saved Markdown files
- Text cleanup, tone adjustment, and summarization
- Streaming partial text
- Remembering the original destination while the user works elsewhere
- Custom vocabulary
- Multiple languages
- Installer-quality support for other computers
- Settings UI
- Hold-to-talk mode

## Product risks

### Focus can change

Automatic paste is directed to the field focused at the end of recording. The interface must explain that the user should return to the destination and keep it focused while transcription completes.

### “Verbatim” is not perfectly literal

Speech-recognition models may add punctuation, omit disfluencies, or mishear words even without an explicit cleanup step. Representative tests are needed before accuracy claims are made.

### Local does not mean zero setup

The application and model must be installed or downloaded. GPU acceleration may require additional runtime dependencies.

### Clipboard behavior is visible

Version 0.1 deliberately leaves the transcript on the clipboard as its recovery mechanism. Windows does not provide a universal way to verify that every application accepted a simulated paste, so insertion is best-effort. Clipboard restoration can be considered after insertion reliability is proven.
