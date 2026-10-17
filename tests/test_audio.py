from __future__ import annotations

import unittest

import numpy as np

from wordwright.audio import (
    AudioRecorder,
    MicrophoneUnavailableError,
    microphone_devices,
    resolve_microphone,
)


class FakeStream:
    def __init__(self, module, **options) -> None:
        self.module = module
        self.options = options

    def start(self) -> None:
        callback = self.options["callback"]
        samples = np.linspace(-1.0, 1.0, self.module.frame_count, dtype=np.float32)
        callback(samples[:, None], samples.size, None, None)

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


class FakeSoundDevice:
    def __init__(self, supported_rates, native_rate, frame_count) -> None:
        self.supported_rates = set(supported_rates)
        self.native_rate = native_rate
        self.frame_count = frame_count
        self.opened_rate = None
        self.last_checked_device = None

    def check_input_settings(self, **options) -> None:
        self.last_checked_device = options["device"]
        if options["samplerate"] not in self.supported_rates:
            raise RuntimeError("unsupported sample rate")

    def query_devices(self, device, kind):
        del device, kind
        return {"default_samplerate": self.native_rate}

    def InputStream(self, **options):
        self.opened_rate = options["samplerate"]
        return FakeStream(self, **options)


class AudioRecorderTests(unittest.TestCase):
    def test_uses_requested_rate_when_microphone_supports_it(self) -> None:
        sounddevice = FakeSoundDevice({16_000}, 48_000, 16_000)
        recorder = AudioRecorder(sounddevice_module=sounddevice)

        recorder.start()
        samples = recorder.stop()

        self.assertEqual(sounddevice.opened_rate, 16_000)
        self.assertEqual(samples.size, 16_000)

    def test_falls_back_to_native_rate_and_resamples(self) -> None:
        sounddevice = FakeSoundDevice({48_000}, 48_000, 48_000)
        recorder = AudioRecorder(sounddevice_module=sounddevice)

        recorder.start()
        samples = recorder.stop()

        self.assertEqual(sounddevice.opened_rate, 48_000)
        self.assertEqual(samples.size, 16_000)
        self.assertEqual(samples.dtype, np.float32)

    def test_resolves_device_provider_each_time_recording_starts(self) -> None:
        sounddevice = FakeSoundDevice({16_000}, 48_000, 16_000)
        selected = [3]
        recorder = AudioRecorder(
            device_provider=lambda: selected[0],
            sounddevice_module=sounddevice,
        )

        recorder.start()
        recorder.stop()

        self.assertEqual(sounddevice.last_checked_device, 3)


class FakeDeviceCatalog:
    def __init__(self) -> None:
        self.default = type("Default", (), {"device": (2, 0)})()

    def query_devices(self):
        return [
            {"name": "Speakers", "max_input_channels": 0, "hostapi": 0},
            {"name": "Headset Mic", "max_input_channels": 1, "hostapi": 0},
            {"name": "Laptop Mic", "max_input_channels": 2, "hostapi": 1},
            {"name": "Headset Mic", "max_input_channels": 1, "hostapi": 1},
        ]

    def query_hostapis(self):
        return [{"name": "MME"}, {"name": "WASAPI"}]


class MicrophoneDeviceTests(unittest.TestCase):
    def test_lists_inputs_with_host_api_labels_and_default(self) -> None:
        devices = microphone_devices(FakeDeviceCatalog())

        self.assertEqual(
            [device.label for device in devices],
            ["Headset Mic — MME", "Laptop Mic", "Headset Mic — WASAPI"],
        )
        self.assertEqual(
            [device.identifier for device in devices],
            ["MME::Headset Mic", "WASAPI::Laptop Mic", "WASAPI::Headset Mic"],
        )
        self.assertEqual([device.is_default for device in devices], [False, True, False])

    def test_resolves_remembered_name_to_current_index(self) -> None:
        self.assertEqual(resolve_microphone("WASAPI::Headset Mic", FakeDeviceCatalog()), 3)
        self.assertIsNone(resolve_microphone(None, FakeDeviceCatalog()))

    def test_missing_preferred_microphone_does_not_fall_back_silently(self) -> None:
        with self.assertRaisesRegex(MicrophoneUnavailableError, "not available"):
            resolve_microphone("AirPods", FakeDeviceCatalog())


if __name__ == "__main__":
    unittest.main()

