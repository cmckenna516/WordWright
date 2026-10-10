from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from wordwright.config import AppConfig
from wordwright.controller import AppController
from wordwright.output import DeliveryResult
from wordwright.state import AppState


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
        self.loads = 0
        self.active_label = "small.en · CPU"

    @property
    def is_loaded(self) -> bool:
        return self.loaded

    def load(self) -> None:
        self.loaded = True
        self.loads += 1

    def transcribe(self, samples) -> str:
        return "Testing one, two, three."


class FakeInserter:
    def __init__(self, result=DeliveryResult.TYPED) -> None:
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

    def make_controller(self, runner=None, inserter=None):
        status = FakeStatus()
        recorder = FakeRecorder()
        transcriber = FakeTranscriber()
        clock = iter(float(value) for value in range(1, 100))
        controller = AppController(
            config=AppConfig(),
            recorder=recorder,
            transcriber=transcriber,
            inserter=inserter or FakeInserter(),
            status=status,
            hotkey=FakeHotkey(),
            async_runner=runner or ImmediateRunner(),
            monotonic=lambda: next(clock),
        )
        return controller, status, recorder, transcriber

    def test_escape_cancels_recording_without_typing(self) -> None:
        inserter = FakeInserter()
        controller, status, recorder, _ = self.make_controller(inserter=inserter)
        controller.start()
        controller.handle_hotkey()

        controller.cancel_recording()

        self.assertTrue(recorder.cancelled)
        self.assertEqual(controller.state, AppState.IDLE)
        self.assertEqual(inserter.texts, [])
        self.assertIn("cancelled", status.messages[-1])

    def test_escape_does_nothing_when_not_recording(self) -> None:
        controller, status, recorder, _ = self.make_controller()
        controller.start()
        messages = list(status.messages)

        controller.cancel_recording()

        self.assertFalse(recorder.cancelled)
        self.assertEqual(controller.state, AppState.IDLE)
        self.assertEqual(status.messages, messages)

    def test_model_change_while_idle_reloads_immediately(self) -> None:
        controller, _, _, transcriber = self.make_controller()
        controller.start()
        configured = []

        controller.reload_model(lambda: configured.append("base.en"))

        self.assertEqual(configured, ["base.en"])
        self.assertEqual(transcriber.loads, 2)
        self.assertEqual(controller.state, AppState.IDLE)

    def test_model_change_while_recording_waits_until_idle(self) -> None:
        controller, _, _, transcriber = self.make_controller()
        controller.start()
        controller.handle_hotkey()
        configured = []

        controller.reload_model(lambda: configured.append("base.en"))
        self.assertEqual(configured, [])
        self.assertEqual(controller.state, AppState.RECORDING)

        controller.cancel_recording()

        self.assertEqual(configured, ["base.en"])
        self.assertEqual(transcriber.loads, 2)
        self.assertEqual(controller.state, AppState.IDLE)

    def test_model_ready_reports_the_active_model(self) -> None:
        controller, status, _, _ = self.make_controller()
        labels = []
        status.set_model_label = labels.append

        controller.start()

        self.assertEqual(labels, ["small.en · CPU"])

    def test_stale_idle_timer_does_not_override_a_newer_state(self) -> None:
        deferred = []

        def runner(function) -> None:
            # Hold back the idle timer and the model-reload worker.
            if getattr(function, "__name__", "") in {"reset", "run"}:
                deferred.append(function)
            else:
                function()

        controller, _, _, _ = self.make_controller(runner=runner)
        controller.start()
        controller.handle_hotkey()
        controller.handle_hotkey()
        self.assertEqual(controller.state, AppState.SUCCESS)

        # A model switch starts while "text typed" is still showing.
        controller.reload_model(lambda: None)
        self.assertEqual(controller.state, AppState.LOADING)
        reset_timer = deferred[0]
        with patch("wordwright.controller.time.sleep"):
            reset_timer()

        self.assertEqual(controller.state, AppState.LOADING)

if __name__ == "__main__":
    unittest.main()
