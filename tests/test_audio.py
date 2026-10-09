from __future__ import annotations

import unittest

import numpy as np

from wordwright.audio import AudioRecorder


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

    def check_input_settings(self, **options) -> None:
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


if __name__ == "__main__":
    unittest.main()

