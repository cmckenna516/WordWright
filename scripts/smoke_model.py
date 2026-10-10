from __future__ import annotations

import argparse
import time
import wave
from pathlib import Path

import numpy as np

from wordwright.hardware import detect_hardware, resolve
from wordwright.transcription import LocalTranscriber


def load_wave(path: Path, target_rate: int = 16_000) -> np.ndarray:
    with wave.open(str(path), "rb") as audio_file:
        channels = audio_file.getnchannels()
        sample_width = audio_file.getsampwidth()
        source_rate = audio_file.getframerate()
        frames = audio_file.readframes(audio_file.getnframes())

    if sample_width != 2:
        raise ValueError("The smoke test expects a 16-bit PCM WAV file.")
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if source_rate != target_rate:
        source_positions = np.arange(samples.size, dtype=np.float64)
        target_size = round(samples.size * target_rate / source_rate)
        target_positions = np.linspace(0, samples.size - 1, target_size)
        samples = np.interp(target_positions, source_positions, samples).astype(
            np.float32
        )
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--audio", type=Path)
    parser.add_argument(
        "--model",
        default="auto",
        help="auto, large-v3-turbo, small.en, or base.en (compare models on this PC)",
    )
    args = parser.parse_args()

    plan = resolve(args.model, detect_hardware())
    print(f"Model: {plan.label} ({plan.reason})")
    transcriber = LocalTranscriber(
        model_name=plan.model,
        device=plan.device,
        compute_type=plan.compute_type,
        download_root=args.model_dir,
    )
    started = time.perf_counter()
    transcriber.load()
    loaded = time.perf_counter()
    audio = load_wave(args.audio) if args.audio else np.zeros(16_000, dtype=np.float32)
    result = transcriber.transcribe(audio)
    finished = time.perf_counter()
    print(f"Model load: {loaded - started:.2f}s")
    print(f"One-second inference: {finished - loaded:.2f}s")
    print(f"Transcript: {result!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
