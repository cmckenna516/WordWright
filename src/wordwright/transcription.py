from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

LOGGER = logging.getLogger(__name__)

_REQUIRED_MODEL_FILES = ("config.json", "model.bin", "tokenizer.json")


def _repository_id(model_name: str) -> str:
    if "/" in model_name:
        return model_name
    try:
        from faster_whisper.utils import _MODELS

        return _MODELS.get(model_name, f"Systran/faster-whisper-{model_name}")
    except ImportError:
        return f"Systran/faster-whisper-{model_name}"


class LocalTranscriber:
    """Load and run a local faster-whisper model."""

    def __init__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        download_root: Path | str | None = None,
        model_factory: Callable[..., Any] | None = None,
        vocabulary_provider: Callable[[], Sequence[str]] | None = None,
        cpu_fallback: tuple[str, str] | None = None,
    ) -> None:
        self._download_root = Path(download_root) if download_root else None
        self._model_factory = model_factory
        self._vocabulary_provider = vocabulary_provider or (lambda: ())
        self._model: Any | None = None
        self.configure(model_name, device, compute_type, cpu_fallback)

    def configure(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        cpu_fallback: tuple[str, str] | None = None,
    ) -> None:
        """Select a different model. It takes effect on the next load()."""

        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._cpu_fallback = cpu_fallback
        self._model = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def active_label(self) -> str:
        return f"{self._model_name} · {'GPU' if self._device == 'cuda' else 'CPU'}"

    def load(self) -> None:
        if self._model is not None:
            return
        try:
            self._load_current()
        except Exception:
            if self._device != "cuda" or self._cpu_fallback is None:
                raise
            LOGGER.exception("GPU model load failed; falling back to the CPU")
            model_name, compute_type = self._cpu_fallback
            self.configure(model_name, "cpu", compute_type)
            self._load_current()

    def _load_current(self) -> None:
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
        LOGGER.info("Loading %s", self.active_label)
        self._model = self._model_factory(model_source, **options)

    def _find_cached_model(self) -> Path | None:
        if self._download_root is None:
            return None
        repository = _repository_id(self._model_name).replace("/", "--")
        snapshots = self._download_root / f"models--{repository}" / "snapshots"
        if not snapshots.is_dir():
            return None
        for snapshot in sorted(snapshots.iterdir(), reverse=True):
            if (
                snapshot.is_dir()
                and all((snapshot / name).is_file() for name in _REQUIRED_MODEL_FILES)
                and any(snapshot.glob("vocabulary.*"))
            ):
                return snapshot
        return None

    def hotwords(self) -> str | None:
        """Vocabulary that biases recognition toward the user's own terms."""

        try:
            terms = [term for term in self._vocabulary_provider() if term]
        except Exception:
            LOGGER.exception("Unable to read the custom vocabulary")
            return None
        return ", ".join(terms) or None

    def transcribe(self, samples: np.ndarray | str | Path) -> str:
        if self._model is None:
            raise RuntimeError("The speech model is not loaded.")

        # hotwords is faster-whisper's term-biasing option: it is placed in
        # Whisper's prompt for every segment, so listed names are spelled the
        # user's way. VAD removes silence first, which keeps the model from
        # filling quiet stretches with listed words. Only roughly the first 220
        # tokens of the list are used.
        segments, _ = self._model.transcribe(
            samples,
            language="en",
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
            word_timestamps=False,
            hotwords=self.hotwords(),
        )
        return "".join(segment.text for segment in segments).strip()
