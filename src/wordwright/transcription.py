from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np


class LocalTranscriber:
    """Load and run a local faster-whisper model."""

    def __init__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        download_root: Path | str | None = None,
        model_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._download_root = Path(download_root) if download_root else None
        self._model_factory = model_factory
        self._model: Any | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        if self._model is not None:
            return
        if self._model_factory is None:
            from faster_whisper import WhisperModel

            self._model_factory = WhisperModel
        options = {
            "device": self._device,
            "compute_type": self._compute_type,
        }
        model_source: str = self._model_name
        if self._download_root is not None:
            self._download_root.mkdir(parents=True, exist_ok=True)
            cached_model = self._find_cached_model()
            if cached_model is not None:
                model_source = str(cached_model)
            else:
                options["download_root"] = str(self._download_root)
        self._model = self._model_factory(model_source, **options)

    def _find_cached_model(self) -> Path | None:
        if self._download_root is None:
            return None
        repository_directory = (
            self._download_root
            / f"models--Systran--faster-whisper-{self._model_name}"
            / "snapshots"
        )
        if not repository_directory.is_dir():
            return None
        required_files = {
            "config.json",
            "model.bin",
            "tokenizer.json",
            "vocabulary.txt",
        }
        for snapshot in sorted(repository_directory.iterdir(), reverse=True):
            if snapshot.is_dir() and all(
                (snapshot / filename).is_file() for filename in required_files
            ):
                return snapshot
        return None


    def transcribe(self, samples: np.ndarray | str | Path) -> str:
        if self._model is None:
            raise RuntimeError("The speech model is not loaded.")

        segments, _ = self._model.transcribe(
            samples,
            language="en",
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
            word_timestamps=False,
        )
        return "".join(segment.text for segment in segments).strip()

