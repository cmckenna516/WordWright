from __future__ import annotations

import threading
from typing import Any

import numpy as np


class AudioRecorder:
    """Capture mono microphone samples in memory."""

    def __init__(
        self,
        sample_rate: int = 16_000,
        device: int | str | None = None,
        sounddevice_module: Any | None = None,
    ) -> None:
        if sounddevice_module is None:
            import sounddevice as sounddevice_module

        self._sd = sounddevice_module
        self._sample_rate = sample_rate
        self._capture_rate = sample_rate
        self._device = device
        self._stream: Any | None = None
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._last_status: str | None = None

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    @property
    def last_status(self) -> str | None:
        return self._last_status

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("A recording is already in progress.")

        with self._lock:
            self._frames = []
            self._last_status = None

        self._capture_rate = self._supported_capture_rate()
        self._stream = self._sd.InputStream(
            samplerate=self._capture_rate,
            channels=1,
            dtype="float32",
            device=self._device,
            callback=self._callback,
        )
        try:
            self._stream.start()
        except Exception:
            self._stream.close()
            self._stream = None
            raise

    def stop(self) -> np.ndarray:
        stream = self._stream
        if stream is None:
            raise RuntimeError("No recording is in progress.")

        self._stream = None
        try:
            stream.stop()
        finally:
            stream.close()

        with self._lock:
            frames = self._frames
            self._frames = []

        if not frames:
            return np.empty(0, dtype=np.float32)
        samples = np.concatenate(frames).astype(np.float32, copy=False)
        return self._resample(samples, self._capture_rate, self._sample_rate)

    def cancel(self) -> None:
        if self._stream is None:
            return
        try:
            self.stop()
        except Exception:
            self._stream = None

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        del frames, time_info
        if status:
            self._last_status = str(status)
        with self._lock:
            self._frames.append(indata[:, 0].copy())

    def _supported_capture_rate(self) -> int:
        try:
            self._sd.check_input_settings(
                device=self._device,
                channels=1,
                dtype="float32",
                samplerate=self._sample_rate,
            )
            return self._sample_rate
        except Exception:
            device = self._sd.query_devices(self._device, "input")
            native_rate = int(round(float(device["default_samplerate"])))
            if native_rate <= 0:
                raise RuntimeError("The default microphone has no usable sample rate.")
            self._sd.check_input_settings(
                device=self._device,
                channels=1,
                dtype="float32",
                samplerate=native_rate,
            )
            return native_rate

    @staticmethod
    def _resample(
        samples: np.ndarray,
        source_rate: int,
        target_rate: int,
    ) -> np.ndarray:
        if samples.size == 0 or source_rate == target_rate:
            return samples.astype(np.float32, copy=False)
        target_length = max(1, int(round(samples.size * target_rate / source_rate)))
        source_positions = np.arange(samples.size, dtype=np.float64)
        target_positions = np.arange(target_length, dtype=np.float64)
        target_positions *= source_rate / target_rate
        return np.interp(target_positions, source_positions, samples).astype(np.float32)


def list_microphones(sounddevice_module: Any | None = None) -> list[str]:
    if sounddevice_module is None:
        import sounddevice as sounddevice_module

    devices = sounddevice_module.query_devices()
    lines: list[str] = []
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) > 0:
            default_marker = " (default)" if index == sounddevice_module.default.device[0] else ""
            lines.append(f"{index}: {device['name']}{default_marker}")
    return lines

