# Product direction, originality, and roadmap

## Product direction

Wordwright is a small, local Windows dictation utility. It has two interface
surfaces with different jobs:

1. A persistent, focus-safe overlay that communicates recording state without
   interrupting the application where the user is typing.
2. A lightweight dark launcher for status, settings, optional local history,
   correction tools, mind maps, statistics, and exports.

The product should remain understandable without onboarding or an account. New
features must not compromise the reliability of the core loop:

`hotkey -> record -> local transcription -> clipboard -> paste`

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
- The launcher uses a plain dark interface with Home, History, and Settings.

The first launcher build intentionally has no dashboard clutter. Home shows
runtime state, the shortcut, model readiness, microphone, and whether history
is enabled.

## Privacy and local storage

History is strictly opt-in and disabled by default.

- Enabling history requires the user to choose a local folder first.
- Transcript text is never written to disk when history is disabled.
- Recorded audio is not retained by history.
- Retention choices are 30, 60, 90 days, or never delete automatically.
- The user can delete individual records, clear all history, and open the
  storage folder.
- Automatic deletion runs locally and should be testable without a network.
- Optional mind maps and correction learning remain disabled unless local
  history is enabled, because both require stored text.
- Every stored record, learned correction, statistic, and mind-map node must be
  reviewable and deletable.

The planned storage format is one SQLite database in the user-selected folder.
SQLite keeps search, retention, correction pairs, and statistics transactional
without requiring a service. Markdown and plain-text exports are generated on
demand.

## Feature roadmap

### Phase 1: dependable utility shell

- Repair the persistent overlay and click-through Win32 behavior.
- Track the active monitor and respect its work area.
- Add the Home, History, and Settings launcher shell.
- Add tray Open, overlay visibility, and Quit actions.
- Persist privacy-safe settings locally.
- Add optional asynchronous start and stop WAV hooks.
- Add rotating local diagnostic logs that never contain transcript bodies.

### Phase 2: user controls

- Editable global hotkey.
- Push-to-talk and hands-free toggle modes.
- Microphone picker with a local live input meter and test.
- `Esc` cancels the current recording without transcription or insertion.
- Launch at Windows sign-in.
- Single-instance packaged executable suitable for pinning to the taskbar.

### Phase 3: opt-in local history

- Folder selection and explicit enable confirmation.
- Local transcript list, search, copy, edit, delete, and retention.
- Pinning to exempt selected entries from automatic deletion.
- Markdown, plain-text, JSON, and CSV exports.
- Central local statistics view: sessions, words, recording time, and estimated
  typing time saved.

Statistics derive from local history. If history is off, persistent statistics
are also off unless a separate aggregate-only option is designed and approved.

### Phase 4: corrections and vocabulary learning

Corrections must be easy, transparent, and reversible.

1. The history editor shows the generated transcript as ordinary editable text.
2. Saving an edit can optionally record a local original/corrected pair.
3. The app proposes vocabulary or replacement rules from repeated corrections.
4. The user reviews and accepts each proposed rule before it affects future
   output.
5. Accepted names, jargon, spellings, and replacements appear in a manageable
   local dictionary.
6. Rules can be disabled, edited, exported, or deleted.

Do not silently train on full transcript history. Start with explainable local
dictionary and replacement behavior. More advanced model adaptation requires a
separate privacy and quality design.

### Phase 5: opt-in local mind maps

Mind maps are generated only from records the user explicitly selects or from a
user-approved local collection.

- Extract topics, projects, people, and relationships locally where practical.
- Always preserve links from a node back to its source transcript records.
- Allow manual rename, merge, connect, disconnect, hide, and delete operations.
- Never imply that an inferred relationship is a verified fact.
- Export maps as Markdown outline, JSON, and an image or portable graph format.
- Deleting a transcript should either remove derived nodes or clearly mark them
  as detached, according to a user-visible rule.

### Later possibilities

- Per-application preferences.
- Reusable snippets and text expansion.
- Additional languages.
- Optional transcript cleanup modes separate from verbatim transcription.
- Retry from retained audio only if a future design explicitly changes the
  current memory-only audio policy.

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

