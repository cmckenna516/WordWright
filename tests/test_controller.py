from __future__ import annotations

import unittest

import numpy as np

from wordwright.config import AppConfig
from wordwright.controller import AppController
from wordwright.output import DeliveryResult
from wordwright.status import AppState


class FakeStatus:
    def __init__(self) -> None:
        self.states = []
        self.messages = []
        self.stopped = False

    def update(self, state) -> None:
        self.states.append(state)

    def notify(self, message, title="Wordwright") -> None:
        self.messages.append(message)

    def stop(self) -> None:
        self.stopped = True


class FakeRecorder:
    def __init__(self) -> None:
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> np.ndarray:
        self.started = False
        return np.zeros(16_000, dtype=np.float32)

    def cancel(self) -> None:
        self.cancelled = True


class FakeTranscriber:
    def __init__(self) -> None:
        self.loaded = False

    def load(self) -> None:
        self.loaded = True

    def transcribe(self, samples) -> str:
        return "Testing one, two, three."


class FakeInserter:
    def __init__(self, result=DeliveryResult.PASTED) -> None:
        self.texts = []
        self.result = result

    def deliver(self, text):
        self.texts.append(text)
        return self.result


class FakeHotkey:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class ImmediateRunner:
    def __call__(self, function) -> None:
        # Skip delayed state-reset closures so state changes remain inspectable.
        if getattr(function, "__name__", "") == "reset":
            return
        function()


class AppControllerTests(unittest.TestCase):
    def test_full_toggle_flow(self) -> None:
        clock_values = iter([1.0, 2.0])
        status = FakeStatus()
        recorder = FakeRecorder()
        transcriber = FakeTranscriber()
        inserter = FakeInserter()
        hotkey = FakeHotkey()
        controller = AppController(
            config=AppConfig(),
            recorder=recorder,
            transcriber=transcriber,
            inserter=inserter,
            status=status,
            hotkey=hotkey,
            async_runner=ImmediateRunner(),
            monotonic=lambda: next(clock_values),
        )

        controller.start()
        self.assertTrue(transcriber.loaded)
        self.assertEqual(controller.state, AppState.IDLE)

        controller.handle_hotkey()
        self.assertTrue(recorder.started)
        self.assertEqual(controller.state, AppState.RECORDING)

        controller.handle_hotkey()
        self.assertEqual(inserter.texts, ["Testing one, two, three."])
        self.assertEqual(controller.state, AppState.SUCCESS)
        self.assertNotIn("\n", inserter.texts[0])

    def test_hotkey_is_ignored_while_model_loads(self) -> None:
        queued = []
        status = FakeStatus()
        controller = AppController(
            config=AppConfig(),
            recorder=FakeRecorder(),
            transcriber=FakeTranscriber(),
            inserter=FakeInserter(),
            status=status,
            hotkey=FakeHotkey(),
            async_runner=queued.append,
            monotonic=lambda: 1.0,
        )
        controller.start()
        controller.handle_hotkey()

        self.assertEqual(controller.state, AppState.LOADING)
        self.assertIn("still loading", status.messages[-1])

    def test_clipboard_fallback_has_a_distinct_success_state(self) -> None:
        clock_values = iter([1.0, 2.0])
        status = FakeStatus()
        controller = AppController(
            config=AppConfig(),
            recorder=FakeRecorder(),
            transcriber=FakeTranscriber(),
            inserter=FakeInserter(DeliveryResult.CLIPBOARD),
            status=status,
            hotkey=FakeHotkey(),
            async_runner=ImmediateRunner(),
            monotonic=lambda: next(clock_values),
        )

        controller.start()
        controller.handle_hotkey()
        controller.handle_hotkey()

        self.assertEqual(controller.state, AppState.CLIPBOARD)
        self.assertIn("copied to the clipboard", status.messages[-1])


if __name__ == "__main__":
    unittest.main()
