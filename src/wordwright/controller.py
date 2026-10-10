from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

import numpy as np

from .config import AppConfig
from .output import DeliveryResult
from .state import AppState

LOGGER = logging.getLogger(__name__)


class AppController:
    """Coordinate hotkey, microphone, transcription, typing, and status."""

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
        hotkey_label: Callable[[], str] = lambda: "Ctrl+Alt+Space",
        save_transcript: Callable[[str, float], None] | None = None,
    ) -> None:
        # Writes a dictation to history; raises if it can't. None or a no-op
        # when history is off (the callable decides).
        self._save_transcript = save_transcript
        self._hotkey_label = hotkey_label
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
        # Serializes start, stop, and cancel, which can arrive from the hotkey
        # listener and the overlay's click handler at the same time.
        self._transition_lock = threading.Lock()
        self._pending_reload: Callable[[], None] | None = None

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
        problem = getattr(self._hotkey, "registration_error", None)
        if problem:
            self._status.notify(f"{problem} You can still start dictation from the scroll.")
        self._run_async(self._load_model)

    def handle_hotkey(self) -> None:
        with self._state_lock:
            now = self._monotonic()
            if now - self._last_hotkey_at < self._config.hotkey_debounce_seconds:
                return
            self._last_hotkey_at = now

        with self._transition_lock:
            state = self.state
            if state is AppState.IDLE:
                self._begin_recording()
            elif state is AppState.RECORDING:
                self._end_recording()
            elif state is AppState.LOADING:
                self._status.notify("The local speech model is still loading.")
            elif state is AppState.TRANSCRIBING:
                self._status.notify("Transcription is already in progress.")
            elif state is AppState.ERROR and not self._transcriber.is_loaded:
                self._status.notify(
                    "The speech model is not loaded. Choose another model under Speech in the app."
                )

    def cancel_recording(self) -> None:
        """Discard the current recording without transcribing or typing it."""

        with self._transition_lock:
            if self.state is not AppState.RECORDING:
                return
            try:
                self._recorder.cancel()
            finally:
                LOGGER.info("Recording cancelled")
                self._enter_idle()
                self._status.notify("Recording cancelled. Nothing was typed.")

    def reload_model(self, configure: Callable[[], None]) -> None:
        """Switch speech models now if idle, otherwise once the app is idle again.

        ``configure`` selects the new model on the transcriber; it runs on a
        worker thread right before the new model loads.
        """

        with self._state_lock:
            if self._shutting_down:
                return
            busy = self._state in {
                AppState.LOADING,
                AppState.RECORDING,
                AppState.TRANSCRIBING,
            }
            if busy:
                self._pending_reload = configure
                return
            self._pending_reload = None
        self._start_reload(configure)

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
            with self._state_lock:
                retry = self._pending_reload is not None
            if retry:
                self._enter_idle()
            return

        if self._shutting_down:
            return
        LOGGER.info("The local speech model is ready")
        set_label = getattr(self._status, "set_model_label", None)
        if set_label is not None:
            set_label(getattr(self._transcriber, "active_label", ""))
        with self._state_lock:
            pending = self._pending_reload
        if pending is not None:
            self._enter_idle()
            return
        self._set_state(AppState.IDLE)
        if getattr(self._hotkey, "registration_error", None):
            self._status.notify("Ready. Select the scroll to start recording.")
        else:
            self._status.notify(f"Ready. Press {self._hotkey_label()} to start recording.")

    def _start_reload(self, configure: Callable[[], None]) -> None:
        self._set_state(AppState.LOADING)

        def run() -> None:
            try:
                configure()
            except Exception as exc:
                LOGGER.exception("Unable to select the speech model")
                self._fail("The speech model setting could not be applied.", exc, recover=False)
                return
            self._load_model()

        self._run_async(run)

    def _enter_idle(self) -> None:
        with self._state_lock:
            pending = self._pending_reload
            self._pending_reload = None
            if self._shutting_down:
                return
        if pending is not None:
            self._start_reload(pending)
        else:
            self._set_state(AppState.IDLE)

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
        self._run_async(lambda: self._transcribe_and_type(samples))

    def _transcribe_and_type(self, samples: np.ndarray) -> None:
        try:
            text = self._transcriber.transcribe(samples)
            if not text:
                self._fail("No speech was detected.")
                return
            with self._state_lock:
                if self._shutting_down:
                    return
            # Save before typing so nothing is lost if typing fails. When the
            # dictation is saved, the clipboard is never used as a fallback.
            saved = self._save(text, samples.size / self._config.sample_rate)
            delivery = self._inserter.deliver(text, clipboard_fallback=not saved)
        except Exception as exc:
            LOGGER.exception("Unable to transcribe or type")
            self._fail(
                "Transcription or typing failed. Check the log for details.",
                exc,
            )
            return

        if delivery is DeliveryResult.NOT_TYPED:
            self._set_state(AppState.SAVED)
            self._status.notify(
                "No text field could take the transcript, so it was saved to your history only."
            )
            self._return_to_idle_after(1.5, AppState.SAVED)
        elif delivery is DeliveryResult.CLIPBOARD:
            self._set_state(AppState.CLIPBOARD)
            self._status.notify(
                "No text field could take the transcript, so it was copied to the clipboard."
            )
            self._return_to_idle_after(1.5, AppState.CLIPBOARD)
        else:
            self._set_state(AppState.SUCCESS)
            self._return_to_idle_after(1.5, AppState.SUCCESS)

    def _save(self, text: str, audio_seconds: float) -> bool:
        if self._save_transcript is None:
            return False
        try:
            return bool(self._save_transcript(text, audio_seconds))
        except Exception as exc:
            # Never log the text itself, only what went wrong.
            LOGGER.warning("Could not save to history (%s: %s)", type(exc).__name__, exc)
            self._status.notify(
                "Couldn't save this dictation to your history folder. Check that it still exists."
            )
            return False

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
            self._return_to_idle_after(2.5, AppState.ERROR)

    def _return_to_idle_after(self, seconds: float, expected: AppState) -> None:
        def reset() -> None:
            time.sleep(seconds)
            # Only reset if nothing else (such as a model reload) has changed
            # the state since this timer was scheduled.
            if self.state is expected:
                self._enter_idle()

        self._run_async(reset)

    def _set_state(self, state: AppState) -> None:
        with self._state_lock:
            self._state = state
        set_cancel = getattr(self._hotkey, "set_cancel_enabled", None)
        if set_cancel is not None:
            # Esc is claimed from other apps only while a recording is running.
            set_cancel(state is AppState.RECORDING)
        self._status.update(state)

    @staticmethod
    def _start_daemon(function: Callable[[], None]) -> None:
        threading.Thread(target=function, daemon=True).start()
