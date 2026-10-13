from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path

import pyperclip

from wordwright.audio import AudioRecorder, list_microphones
from wordwright.hardware import detect_hardware, recommend
from wordwright.hotkeys import create_hotkeys
from wordwright.transcription import LocalTranscriber


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Wordwright's microphone, model, clipboard, and hotkey."
    )
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    return parser.parse_args()


def verify_microphone() -> None:
    microphones = list_microphones()
    if not microphones:
        raise RuntimeError("No microphone input device was found.")

    recorder = AudioRecorder()
    recorder.start()
    try:
        time.sleep(0.5)
        samples = recorder.stop()
    except Exception:
        recorder.cancel()
        raise
    if samples.size == 0:
        raise RuntimeError("The default microphone opened but returned no audio samples.")
    print(f"Microphone check passed ({samples.size} samples captured).")


def verify_model(model_directory: Path, audio_path: Path) -> None:
    if not audio_path.is_file():
        raise RuntimeError(f"Verification audio is missing: {audio_path}")
    # Download and test the model the app will choose on this machine.
    profile = detect_hardware()
    plan = recommend(profile)
    print(f"Speech model for this PC: {plan.label} ({plan.reason})")
    fallback = (
        (plan.fallback.model, plan.fallback.compute_type, plan.fallback.beam_size)
        if plan.fallback
        else None
    )
    transcriber = LocalTranscriber(
        model_name=plan.model,
        device=plan.device,
        compute_type=plan.compute_type,
        download_root=model_directory,
        cpu_fallback=fallback,
        cpu_threads=profile.cpu_threads,
        beam_size=plan.beam_size,
    )
    transcriber.load()
    transcript = transcriber.transcribe(audio_path)
    if not transcript:
        raise RuntimeError("The speech model loaded but returned an empty transcript.")
    print(f'Speech-model check passed: "{transcript}"')


def verify_clipboard() -> None:
    # The clipboard is only a fallback now (no text field focused), but it
    # still has to work so a dictation is never lost.
    def retry(operation, attempts: int = 20):
        last_error = None
        for attempt in range(attempts):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(0.05)
        raise RuntimeError("Windows clipboard remained unavailable.") from last_error

    previous = retry(pyperclip.paste)
    marker = f"wordwright-preflight-{uuid.uuid4()}"
    try:
        retry(lambda: pyperclip.copy(marker))
        if retry(pyperclip.paste) != marker:
            raise RuntimeError("Clipboard text could not be read back.")
    finally:
        retry(lambda: pyperclip.copy(previous))
    print("Clipboard check passed.")


def verify_hotkey_hook() -> None:
    # Register and release an unlikely shortcut to prove the hotkey system
    # works. The user's own shortcut is checked when the app starts.
    hotkeys = create_hotkeys(
        toggle_spec="ctrl+shift+f12",
        hold_spec="ctrl+alt",
        on_toggle=lambda: None,
        on_hold_start=lambda: None,
        on_hold_stop=lambda: None,
        on_cancel=lambda: None,
    )
    hotkeys.start()
    try:
        hotkeys.wait_until_ready()
    finally:
        hotkeys.stop()
        hotkeys.join(timeout=1.0)
    print("Global hotkey check passed.")


def main() -> int:
    args = parse_args()
    print("Running Wordwright functional checks...")
    verify_microphone()
    verify_model(args.model_dir, args.audio)
    verify_clipboard()
    verify_hotkey_hook()
    print("All Wordwright functional checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

