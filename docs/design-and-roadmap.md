# Product direction, originality, and roadmap

## Product direction

Wordwright is a small, local Windows dictation utility. It has two interface
surfaces with different jobs:

1. A persistent, focus-safe overlay that communicates recording state without
   interrupting the application where the user is typing.
2. A lightweight dark launcher for status, custom vocabulary, the speech
   model, settings, and the planned transcript archive.

The product should remain understandable without onboarding or an account. New
features must not compromise the reliability of the core loop:

`hotkey -> record -> local transcription -> type at the cursor`

The clipboard is touched only when no text field has focus, so a dictation is
never lost. That fallback is replaced by the archive once it exists.

## Originality and provenance

Wordwright may learn from common desktop interaction patterns, but its visual
design and implementation must remain independently produced.

- Do not copy another product's source code, screenshots, icons, illustrations,
  animation frames, interface text, sound effects, or distinctive visual
  composition.
- Use ordinary platform conventions only as functional references: a system
  tray menu, a status overlay, a settings screen, navigation, and local history
  are general interaction patterns.
- Maintain Wordwright's own name, scroll-and-feather identity, colors,
  dimensions, motion, copy, and information hierarchy.
- Record the source and license for every third-party asset added to the
  repository. Prefer original, public-domain, or clearly licensed assets.
- User-selected sound files remain outside the repository. Bundled sounds must
  have documented redistribution rights.
- Do not describe the interface as a clone of another product in documentation,
  packaging, or marketing.

These development rules reduce avoidable provenance risk; they are not a legal
opinion or a substitute for legal advice before public distribution.

## Overlay interaction model

The overlay exists whenever Wordwright is running unless the user disables
the always-visible idle state.

- It stays above ordinary desktop windows and does not receive typing focus.
- It is click-through in the initial implementation.
- It follows the monitor containing the foreground window and remains inside
  that monitor's work area.
- The initial position is top center. Bottom center, left center, and right
  center are user-selectable.
- A future reposition mode may allow dragging without making the normal overlay
  intercept pointer input.
- Display changes, sleep/wake, and Windows shell restarts require explicit
  recovery testing.
- Exclusive full-screen applications may prevent ordinary topmost overlays
  from appearing. Sound and tray feedback remain fallbacks.

### Overlay states

| State | Visual behavior |
| --- | --- |
| Loading | Compact scroll with yellow badge |
| Idle | Compact scroll with neutral badge |
| Recording | Expanded scroll, red badge, restrained breathing motion |
| Transcribing | Expanded scroll, blue badge, restrained pulse |
| Success | Brief green confirmation before returning to idle |
| Error | Brief purple error state plus a visible notification |

## Launcher behavior

- Starting the packaged application opens a single launcher window.
- Starting it again should focus the existing process rather than creating a
  second recorder or hotkey listener.
- Closing the launcher window hides it while dictation continues.
- `Quit Wordwright` fully stops the hotkey, microphone, overlay, and tray
  process.
- The tray menu provides Open, current status, overlay visibility, and Quit.
- The launcher uses a plain dark interface with Dictate, Speech, Settings, and
  History.

The first launcher build intentionally has no dashboard clutter. Home shows
runtime state, the shortcut, model readiness, microphone, and whether history
is enabled.

## Privacy and local storage

The transcript archive is strictly opt-in and disabled by default.

- Enabling it requires the user to choose a local folder first.
- Transcript text is never written to disk while it is disabled.
- Recorded audio is never retained.
- The archive is a single running file in the chosen folder that the user can
  open, edit, move, or delete with ordinary tools.

## Feature roadmap

Scope is deliberately small: Wordwright is a personal tool shared as is, not a
supported product.

### Done

- Persistent, focus-safe overlay that follows the active monitor.
- Launcher with tray Open, overlay visibility, and Quit.
- Optional start and stop WAV cues; rotating logs without transcript text.
- Custom vocabulary that biases recognition toward the user's own names and
  terms.
- Automatic speech-model choice for the machine (GPU, capable CPU, ARM64 or
  lighter CPU), with a manual override.
- Typing the transcript at the cursor instead of pasting through the clipboard.
- `Esc` cancels the current recording without transcription or typing.
- Shortcut registered with Windows so it fires only on the exact combination,
  and can be changed in Settings.
- An idle overlay that redraws only when something changes.

### Next

- Running transcript archive in a folder the user chooses.

### Later possibilities, not committed

- Microphone picker.
- Launch at Windows sign-in.
- Additional languages.

## Sound direction

The intended sound identity is an understated pen-and-scroll motif rather than
generic notification beeps.

- Start and stop sounds are separate user-selected WAV files.
- Playback is asynchronous and must never delay microphone capture.
- Recommended duration is below 300 milliseconds.
- Settings include enable/disable, file selection, and preview.
- No sound is bundled until its origin and redistribution license are recorded.

## Decision rule for new features

Before adding a feature, answer:

1. Does it improve dictation, recovery, or user control?
2. Can it remain local and off by default when it stores personal text?
3. Is its behavior explainable and reversible?
4. Does it preserve the reliability of the core dictation loop?
5. Is every external asset or dependency's provenance documented?

If any answer is no, defer the feature or redesign it.

