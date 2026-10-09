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

