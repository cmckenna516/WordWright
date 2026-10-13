# Technical plan: version 0.1

## Objective

Prove the smallest reliable Windows workflow:

`global hotkey -> microphone recording -> local transcription -> clipboard -> paste`

Desktop polish and distribution come after that loop works in representative applications.

## Provisional architecture

```text
Global hotkey
    |
Recording controller ----> Status indicator
    |
Microphone samples
    |
Local transcription engine
    |
Clipboard
    |
Paste into focused field
```

Each component should have a narrow responsibility so that the speech engine or interface can be replaced without rewriting the workflow.

## Recommended prototype stack

- **Language:** Python, for fast iteration and approachable code.
- **Speech engine:** `faster-whisper` as the first candidate.
- **Audio capture:** a lightweight PortAudio-based Python library such as `sounddevice`.
- **Windows integration:** a global-hotkey library plus minimal Win32 integration where necessary.
- **Status:** a system-tray icon plus a permanent click-through scroll overlay at the top center, with compact idle, expanded recording, pulsing processing, success, and error states.
- **Text delivery:** Windows clipboard followed by a paste command.
- **Packaging:** defer until the workflow is validated; evaluate PyInstaller only after the spike.

These choices are provisional. The technical spike, not preference, should decide the final libraries.

## Model strategy

Start with an English-only small Whisper model. It should provide a good balance of punctuation, accuracy, model size, and response time.

Benchmark at least:

1. A small English model for responsiveness.
2. A medium English model for improved recognition.
3. CPU inference as the compatibility baseline.
4. NVIDIA GPU inference on the development RTX 3070 Ti.

The Ryzen 9 5900X and 32 GB RAM are sufficient for a CPU fallback. The RTX 3070 Ti should make larger models practical, but GPU runtime and packaging complexity must be measured rather than assumed.

If `faster-whisper` becomes difficult to package reliably on Windows, evaluate `whisper.cpp` as the next candidate. Do not integrate multiple engines in version 0.1.

## Implementation order

### 1. Transcription spike

- Transcribe a known English audio file locally.
- Confirm operation with networking disabled after the model is present.
- Record elapsed time and memory use.
- Compare small and medium English models.
- Select one model for the interactive prototype.

### 2. Microphone spike

- List available microphones.
- Capture a short recording.
- Feed captured audio directly to the selected model.
- Avoid permanent audio files.
- Handle a disconnected or unavailable microphone.

### 3. Hotkey-controlled workflow

- Register `Ctrl+Shift+Space` globally for toggle dictation.
- Track `Ctrl+Alt` press and release events for hold-to-dictate.
- A toggle press starts or stops recording; a hold press starts and its release stops.
- Allow both bindings to be configured independently and reject overlaps.
- Prevent overlapping sessions.
- Ensure the hotkey itself is not inserted into the target field.

### 4. Text insertion

- Put the transcript on the clipboard.
- Paste into the currently focused control.
- Never synthesize Enter.
- Test delayed paste behavior across target applications.
- Keep the transcript on the clipboard after the attempt.

### 5. Status interface

- Add a tray icon and permanent top-center overlay that never receive keyboard focus or intercept pointer input during normal operation.
- Represent idle, recording, transcribing, success, and failure.
- Add optional short sounds only if they improve confidence without becoming distracting.

### 6. Packaging

- Produce a repeatable developer setup first.
- Then evaluate a standalone Windows build.
- Treat model download and GPU dependencies as explicit installation concerns.
- Do not build an installer or updater until the prototype is useful.

## State rules

- Only one recording or transcription session may exist at a time.
- A stop command is ignored when idle.
- A start command is rejected while transcription is active.
- Unexpected failures return the application to idle.
- The status indicator must reflect the actual state, not the requested state.
- Closing the application while recording must stop microphone capture safely.

## Test recordings

Create a small private benchmark set using the intended speaker and microphone:

- Clear speech at a normal pace
- Fast speech
- Deliberate mumbling
- Background fan or keyboard noise
- Technical terms and proper names
- Self-correction and repeated phrases
- A 30-second paragraph
- A several-minute passage

Store benchmark recordings outside the repository unless they are intentionally safe to commit.

## Text-field compatibility matrix

Test each candidate build against:

| Target | Expected result |
| --- | --- |
| Windows Notepad | Text appears at caret |
| Browser `textarea` | Text appears without submitting |
| Browser content-editable field | Text appears without submitting |
| Codex composer | Text appears without submitting |
| Multiline field with existing text | Text inserts at current caret |
| No editable control focused | Paste is attempted; transcript remains on the clipboard for manual recovery |

Applications such as Word, Outlook, Slack, and Teams can be tested after the core matrix succeeds.

## Security and privacy notes

- Do not log transcript bodies.
- Do not retain raw microphone audio.
- Do not add analytics or crash-report uploads in version 0.1.
- Pin and document dependencies before distribution.
- Make model origin and download behavior visible in setup documentation.
- Avoid claiming that output is perfectly accurate.

## Decision gates

Before building a polished desktop shell, answer with measurements:

- Which model gives acceptable accuracy on the private benchmark?
- How long does a 30-second recording take to transcribe on CPU and GPU?
- Does clipboard paste work consistently across the core compatibility matrix?
- Can the selected engine be installed reproducibly on a clean Windows machine?
- Does the permanent scroll overlay provide enough feedback without becoming distracting?

If the core loop is unreliable, fix it before adding settings, archives, system audio, or meeting features.
