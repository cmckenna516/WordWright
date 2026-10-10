from __future__ import annotations

import logging
import time
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
        cpu_fallback: tuple[str, str, int] | tuple[str, str] | None = None,
        cpu_threads: int = 0,
        beam_size: int = 5,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._cpu_threads = cpu_threads
        self._clock = clock
        self._download_root = Path(download_root) if download_root else None
        self._model_factory = model_factory
        self._vocabulary_provider = vocabulary_provider or (lambda: ())
        self._model: Any | None = None
        self.configure(model_name, device, compute_type, cpu_fallback, beam_size)

    def configure(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        cpu_fallback: tuple[str, str, int] | tuple[str, str] | None = None,
        beam_size: int = 5,
    ) -> None:
        """Select a different model. It takes effect on the next load()."""

        self._beam_size = max(1, beam_size)
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
            model_name, compute_type, *rest = self._cpu_fallback
            beam_size = rest[0] if rest else self._beam_size
            self.configure(model_name, "cpu", compute_type, beam_size=beam_size)
            self._load_current()

    def _load_current(self) -> None:
        if self._model_factory is None:
            from faster_whisper import WhisperModel

            self._model_factory = WhisperModel
        options: dict[str, Any] = {
            "device": self._device,
            "compute_type": self._compute_type,
        }
        if self._device == "cpu" and self._cpu_threads > 0:
            options["cpu_threads"] = self._cpu_threads
        model_source: str = self._model_name
        if self._download_root is not None:
            self._download_root.mkdir(parents=True, exist_ok=True)
            cached_model = self._find_cached_model()
            if cached_model is not None:
                model_source = str(cached_model)
            else:
                options["download_root"] = str(self._download_root)
        LOGGER.info("Loading %s", self.active_label)
        started = self._clock()
        model = self._model_factory(model_source, **options)
        # Warm up before reporting ready. The first transcription pays one-time
        # costs (voice-detection model load, memory setup) that otherwise land on
        # the user's first dictation. On a GPU this also surfaces missing CUDA
        # libraries here, where load() can still fall back to the CPU.
        self._warm_up(model)
        self._model = model
        LOGGER.info("%s ready in %.1f s", self.active_label, self._clock() - started)

    @staticmethod
    def _warm_up(model: Any) -> None:
        silence = np.zeros(16_000, dtype=np.float32)
        # VAD on silence loads the voice-detection model and skips the encoder.
        list(model.transcribe(silence, language="en", vad_filter=True)[0])
        # Faint noise without VAD runs the encoder and decoder once.
        noise = np.random.default_rng(0).normal(0, 1e-3, 16_000).astype(np.float32)
        list(model.transcribe(noise, language="en", beam_size=1, vad_filter=False)[0])

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
        started = self._clock()
        segments, _ = self._model.transcribe(
            samples,
            language="en",
            task="transcribe",
            beam_size=self._beam_size,
            vad_filter=True,
            condition_on_previous_text=False,
            word_timestamps=False,
            hotwords=self.hotwords(),
        )
        # Segments are generated lazily, so joining them is the actual work.
        text = "".join(segment.text for segment in segments).strip()
        self._log_timing(samples, self._clock() - started)
        return text

    def _log_timing(self, samples: np.ndarray | str | Path, elapsed: float) -> None:
        """Log speed only, never transcript text, to tune model choice per PC."""

        if not isinstance(samples, np.ndarray) or samples.size == 0:
            return
        audio_seconds = samples.size / 16_000
        threads = f", {self._cpu_threads} threads" if self._device == "cpu" and self._cpu_threads else ""
        threads += f", beam {self._beam_size}"
        LOGGER.info(
            "Transcribed %.1f s of audio in %.2f s (%.2fx real time) with %s%s",
            audio_seconds,
            elapsed,
            elapsed / audio_seconds,
            self.active_label,
            threads,
        )
