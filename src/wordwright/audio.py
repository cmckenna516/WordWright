from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
import threading
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class MicrophoneDevice:
    """A stable, user-facing description of an input device."""

    identifier: str
    label: str
    index: int
    is_default: bool = False


class MicrophoneUnavailableError(RuntimeError):
    """The user's preferred input is not currently exposed by Windows."""


class AudioRecorder:
    """Capture mono microphone samples in memory."""

    def __init__(
        self,
        sample_rate: int = 16_000,
        device: int | str | None = None,
        device_provider: Callable[[], int | str | None] | None = None,
        sounddevice_module: Any | None = None,
    ) -> None:
        if sounddevice_module is None:
            import sounddevice as sounddevice_module

        self._sd = sounddevice_module
        self._sample_rate = sample_rate
        self._capture_rate = sample_rate
        self._device = device
        self._device_provider = device_provider
        self._active_device: int | str | None = device
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

        self._active_device = (
            self._device_provider() if self._device_provider is not None else self._device
        )
        self._capture_rate = self._supported_capture_rate()
        self._stream = self._sd.InputStream(
            samplerate=self._capture_rate,
            channels=1,
            dtype="float32",
            device=self._active_device,
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
                device=self._active_device,
                channels=1,
                dtype="float32",
                samplerate=self._sample_rate,
            )
            return self._sample_rate
        except Exception:
            device = self._sd.query_devices(self._active_device, "input")
            native_rate = int(round(float(device["default_samplerate"])))
            if native_rate <= 0:
                raise RuntimeError("The default microphone has no usable sample rate.")
            self._sd.check_input_settings(
                device=self._active_device,
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


def microphone_devices(sounddevice_module: Any | None = None) -> list[MicrophoneDevice]:
    if sounddevice_module is None:
        import sounddevice as sounddevice_module

    devices = sounddevice_module.query_devices()
    try:
        hostapis = sounddevice_module.query_hostapis()
    except (AttributeError, TypeError):
        hostapis = []
    try:
        default_index = int(sounddevice_module.default.device[0])
    except (AttributeError, IndexError, TypeError, ValueError):
        default_index = -1

    candidates: list[tuple[int, str, str]] = []
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) > 0:
            name = str(device["name"])
            hostapi_name = ""
            try:
                hostapi_name = str(hostapis[int(device.get("hostapi", -1))]["name"])
            except (IndexError, KeyError, TypeError, ValueError):
                pass
            candidates.append((index, name, hostapi_name))

    name_counts = Counter(name for _, name, _ in candidates)
    labels = [
        f"{name} — {hostapi}" if name_counts[name] > 1 and hostapi else name
        for _, name, hostapi in candidates
    ]
    label_counts = Counter(labels)
    result: list[MicrophoneDevice] = []
    for (index, _name, _hostapi), label in zip(candidates, labels, strict=True):
        duplicate_label = label_counts[label] > 1
        if duplicate_label:
            label = f"{label} [{index}]"
        identifier = f"{_hostapi}::{_name}" if _hostapi else _name
        if duplicate_label:
            identifier = f"{identifier}::#{index}"
        result.append(
            MicrophoneDevice(
                identifier=identifier,
                label=label,
                index=index,
                is_default=index == default_index,
            )
        )
    return result


def resolve_microphone(
    identifier: str | None,
    sounddevice_module: Any | None = None,
) -> int | None:
    """Resolve a remembered device name to its current PortAudio index."""

    if identifier is None:
        return None
    for device in microphone_devices(sounddevice_module):
        if device.identifier == identifier:
            return device.index
    raise MicrophoneUnavailableError(
        f'The selected microphone "{identifier}" is not available. '
        "Connect it or choose another microphone in Settings."
    )


def list_microphones(sounddevice_module: Any | None = None) -> list[str]:
    return [
        f"{device.index}: {device.label}{' (default)' if device.is_default else ''}"
        for device in microphone_devices(sounddevice_module)
    ]

