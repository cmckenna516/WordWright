from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

import numpy as np

from .config import AppConfig
from .output import DeliveryResult
from .status import AppState

LOGGER = logging.getLogger(__name__)


class AppController:
    """Coordinate hotkey, microphone, transcription, paste, and status."""

    def __init__(
        self,
        config: AppConfig,
        recorder: Any,
        transcriber: Any,
        inserter: Any,
        status: Any,
        hotkey: Any | None = None,
        async_runner: Callable[[Callable[[], None]], None] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._recorder = recorder
        self._transcriber = transcriber
        self._inserter = inserter
        self._status = status
        self._hotkey = hotkey
        self._run_async = async_runner or self._start_daemon
        self._monotonic = monotonic
        self._state = AppState.LOADING
        self._state_lock = threading.RLock()
        self._last_hotkey_at = float("-inf")
        self._shutting_down = False

    @property
    def state(self) -> AppState:
        with self._state_lock:
            return self._state

    def attach_hotkey(self, hotkey: Any) -> None:
        self._hotkey = hotkey

    def start(self) -> None:
        if self._hotkey is None:
            raise RuntimeError("A global hotkey must be attached before startup.")
        self._set_state(AppState.LOADING)
        self._hotkey.start()
        self._run_async(self._load_model)

    def handle_hotkey(self) -> None:
        with self._state_lock:
            now = self._monotonic()
            if now - self._last_hotkey_at < self._config.hotkey_debounce_seconds:
                return
            self._last_hotkey_at = now
            state = self._state

        if state is AppState.IDLE:
            self._begin_recording()
        elif state is AppState.RECORDING:
            self._end_recording()
        elif state is AppState.LOADING:
            self._status.notify("The local speech model is still loading.")
        elif state is AppState.TRANSCRIBING:
            self._status.notify("Transcription is already in progress.")

    def shutdown(self) -> None:
        with self._state_lock:
            if self._shutting_down:
                return
            self._shutting_down = True
        try:
            self._recorder.cancel()
        finally:
            if self._hotkey is not None:
                self._hotkey.stop()
            self._status.stop()

    def _load_model(self) -> None:
        LOGGER.info("Loading the local speech model")
        try:
            self._transcriber.load()
        except Exception as exc:
            LOGGER.exception("Unable to load the local speech model")
            self._fail(
                "The speech model could not be loaded. Check the setup and internet connection for the first download.",
                exc,
                recover=False,
            )
            return

        if not self._shutting_down:
            LOGGER.info("The local speech model is ready")
            self._set_state(AppState.IDLE)
            self._status.notify("Ready. Press Ctrl+Alt+Space to start recording.")

    def _begin_recording(self) -> None:
        try:
            self._recorder.start()
        except Exception as exc:
            LOGGER.exception("Unable to start microphone capture")
            self._fail("The microphone could not be opened.", exc)
            return
        self._set_state(AppState.RECORDING)

    def _end_recording(self) -> None:
        try:
            samples = self._recorder.stop()
        except Exception as exc:
            LOGGER.exception("Unable to stop microphone capture")
            self._fail("The recording could not be completed.", exc)
            return

        minimum_samples = int(
            self._config.sample_rate * self._config.minimum_recording_seconds
        )
        if samples.size < minimum_samples:
            self._fail("The recording was too short. Please try again.")
            return

        self._set_state(AppState.TRANSCRIBING)
        self._run_async(lambda: self._transcribe_and_paste(samples))

    def _transcribe_and_paste(self, samples: np.ndarray) -> None:
        try:
            text = self._transcriber.transcribe(samples)
            if not text:
                self._fail("No speech was detected.")
                return
            with self._state_lock:
                if self._shutting_down:
                    return
            delivery = self._inserter.deliver(text)
        except Exception as exc:
            LOGGER.exception("Unable to transcribe or paste")
            self._fail(
                "Transcription failed. If text reached the clipboard, paste it manually.",
                exc,
            )
            return

        if delivery is DeliveryResult.CLIPBOARD:
            self._set_state(AppState.CLIPBOARD)
            self._status.notify(
                "No active text field was found. The transcript was copied to the clipboard."
            )
        else:
            self._set_state(AppState.SUCCESS)
            self._status.notify(
                "Paste command sent. The transcript remains on the clipboard as a backup."
            )
        self._return_to_idle_after(1.5)

    def _fail(
        self,
        message: str,
        error: Exception | None = None,
        recover: bool = True,
    ) -> None:
        if error is not None:
            LOGGER.error("%s (%s)", message, type(error).__name__)
        self._set_state(AppState.ERROR)
        self._status.notify(message)
        if recover:
            self._return_to_idle_after(2.5)

    def _return_to_idle_after(self, seconds: float) -> None:
        def reset() -> None:
            time.sleep(seconds)
            if not self._shutting_down:
                self._set_state(AppState.IDLE)

        self._run_async(reset)

    def _set_state(self, state: AppState) -> None:
        with self._state_lock:
            self._state = state
        self._status.update(state)

    @staticmethod
    def _start_daemon(function: Callable[[], None]) -> None:
        threading.Thread(target=function, daemon=True).start()
