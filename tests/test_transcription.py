from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from wordwright.transcription import LocalTranscriber


class FakeModel:
    def __init__(self, *args, **kwargs) -> None:
        self.init_args = args
        self.init_kwargs = kwargs
        self.transcribe_kwargs = None

    def transcribe(self, samples, **kwargs):
        self.transcribe_kwargs = kwargs
        return iter(
            [SimpleNamespace(text=" Hello,"), SimpleNamespace(text=" world.")]
        ), SimpleNamespace(language="en")


class LocalTranscriberTests(unittest.TestCase):
    def test_loads_model_and_returns_joined_text(self) -> None:
        created = []

        def factory(*args, **kwargs):
            model = FakeModel(*args, **kwargs)
            created.append(model)
            return model

        model_directory = Path(".test-model-cache/download").resolve()
        transcriber = LocalTranscriber(
            "small.en",
            "cpu",
            "int8",
            model_directory,
            factory,
        )
        transcriber.load()
        result = transcriber.transcribe(np.zeros(16_000, dtype=np.float32))

        self.assertEqual(result, "Hello, world.")
        self.assertEqual(created[0].init_args, ("small.en",))
        self.assertEqual(created[0].init_kwargs["device"], "cpu")
        self.assertEqual(
            created[0].init_kwargs["download_root"], str(model_directory)
        )
        self.assertEqual(created[0].transcribe_kwargs["language"], "en")
        self.assertTrue(created[0].transcribe_kwargs["vad_filter"])
        self.assertIsNone(created[0].transcribe_kwargs["hotwords"])

    def test_custom_vocabulary_is_passed_as_hotwords(self) -> None:
        model = FakeModel()
        vocabulary = ["Trace3", "Glean"]
        transcriber = LocalTranscriber(
            "small.en",
            "cpu",
            "int8",
            model_factory=lambda *args, **kwargs: model,
            vocabulary_provider=lambda: vocabulary,
        )
        transcriber.load()
        transcriber.transcribe(np.zeros(16_000, dtype=np.float32))
        self.assertEqual(model.transcribe_kwargs["hotwords"], "Trace3, Glean")

        # Edits apply to the next dictation without reloading the model.
        vocabulary.append("n8n")
        transcriber.transcribe(np.zeros(16_000, dtype=np.float32))
        self.assertEqual(model.transcribe_kwargs["hotwords"], "Trace3, Glean, n8n")

    def test_cpu_threads_apply_on_cpu_only(self) -> None:
        calls = []

        def factory(*args, **kwargs):
            calls.append(kwargs)
            if kwargs["device"] == "cuda":
                raise RuntimeError("no GPU")
            return FakeModel()

        LocalTranscriber("small.en", "cpu", "int8", model_factory=factory, cpu_threads=8).load()
        self.assertEqual(calls[-1]["cpu_threads"], 8)

        calls.clear()
        LocalTranscriber(
            "large-v3-turbo", "cuda", "float16", model_factory=factory,
            cpu_fallback=("small.en", "int8"), cpu_threads=8,
        ).load()
        self.assertNotIn("cpu_threads", calls[0])
        self.assertEqual(calls[1]["cpu_threads"], 8)

    def test_logs_speed_but_never_transcript_text(self) -> None:
        ticks = iter([10.0, 11.5])
        transcriber = LocalTranscriber(
            "base.en", "cpu", "int8",
            model_factory=lambda *args, **kwargs: FakeModel(),
            cpu_threads=8,
            clock=lambda: next(ticks),
        )
        transcriber.load()
        with self.assertLogs("wordwright.transcription", level="INFO") as logs:
            transcriber.transcribe(np.zeros(16_000 * 15, dtype=np.float32))

        line = logs.output[-1]
        self.assertIn("Transcribed 15.0 s of audio in 1.50 s (0.10x real time)", line)
        self.assertIn("base.en · CPU, 8 threads", line)
        self.assertNotIn("Hello", line)

    def test_gpu_failure_falls_back_to_the_cpu(self) -> None:
        calls = []

        def factory(*args, **kwargs):
            calls.append((args, kwargs))
            if kwargs["device"] == "cuda":
                raise RuntimeError("cuDNN missing")
            return FakeModel()

        transcriber = LocalTranscriber(
            "large-v3-turbo",
            "cuda",
            "float16",
            model_factory=factory,
            cpu_fallback=("small.en", "int8"),
        )
        transcriber.load()

        self.assertTrue(transcriber.is_loaded)
        self.assertEqual(calls[-1][0], ("small.en",))
        self.assertEqual(calls[-1][1]["device"], "cpu")
        self.assertEqual(transcriber.active_label, "small.en · CPU")

    def test_cpu_failure_is_not_hidden(self) -> None:
        def factory(*args, **kwargs):
            raise RuntimeError("download failed")

        transcriber = LocalTranscriber("small.en", "cpu", "int8", model_factory=factory)
        with self.assertRaises(RuntimeError):
            transcriber.load()

    def test_finds_cached_models_outside_the_systran_namespace(self) -> None:
        model_directory = Path(".test-model-cache/turbo").resolve()
        snapshot = (
            model_directory
            / "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo"
            / "snapshots"
            / "test-snapshot"
        )
        snapshot.mkdir(parents=True, exist_ok=True)
        for filename in ("config.json", "model.bin", "tokenizer.json", "vocabulary.json"):
            (snapshot / filename).touch()
        calls = []

        def factory(*args, **kwargs):
            calls.append((args, kwargs))
            return FakeModel()

        transcriber = LocalTranscriber(
            "large-v3-turbo", "cpu", "int8", model_directory, factory
        )
        transcriber.load()

        self.assertEqual(calls[0][0], (str(snapshot),))

    def test_loads_existing_snapshot_without_download_request(self) -> None:
        model_directory = Path(".test-model-cache/cached").resolve()
        snapshot = (
            model_directory
            / "models--Systran--faster-whisper-small.en"
            / "snapshots"
            / "test-snapshot"
        )
        snapshot.mkdir(parents=True, exist_ok=True)
        for filename in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
            (snapshot / filename).touch()
        calls = []

        def factory(*args, **kwargs):
            calls.append((args, kwargs))
            return FakeModel()

        transcriber = LocalTranscriber(
            "small.en", "cpu", "int8", model_directory, factory
        )
        transcriber.load()

        self.assertEqual(calls[0][0], (str(snapshot),))
        self.assertNotIn("download_root", calls[0][1])

    def test_incomplete_snapshot_resumes_download(self) -> None:
        model_directory = Path(".test-model-cache/incomplete").resolve()
        snapshot = (
            model_directory
            / "models--Systran--faster-whisper-small.en"
            / "snapshots"
            / "test-snapshot"
        )
        snapshot.mkdir(parents=True, exist_ok=True)
        (snapshot / "model.bin").touch()
        calls = []

        def factory(*args, **kwargs):
            calls.append((args, kwargs))
            return FakeModel()

        transcriber = LocalTranscriber(
            "small.en", "cpu", "int8", model_directory, factory
        )
        transcriber.load()

        self.assertEqual(calls[0][0], ("small.en",))
        self.assertEqual(calls[0][1]["download_root"], str(model_directory))



if __name__ == "__main__":
    unittest.main()

