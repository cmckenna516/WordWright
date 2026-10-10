from __future__ import annotations

import unittest

from wordwright.hardware import HardwareProfile, recommend, resolve


def profile(**overrides) -> HardwareProfile:
    values = dict(native_arm64=False, logical_cpus=24, memory_gb=32.0, cuda_ready=False)
    values.update(overrides)
    return HardwareProfile(**values)


class ModelSelectionTests(unittest.TestCase):
    def test_gpu_desktop_gets_the_most_accurate_model_with_cpu_fallback(self) -> None:
        plan = recommend(profile(cuda_ready=True))

        self.assertEqual((plan.model, plan.device, plan.compute_type), ("large-v3-turbo", "cuda", "float16"))
        self.assertEqual(plan.fallback.model, "small.en")
        self.assertEqual(plan.fallback.device, "cpu")

    def test_capable_cpu_without_gpu_keeps_small(self) -> None:
        plan = recommend(profile())

        self.assertEqual((plan.model, plan.device), ("small.en", "cpu"))

    def test_arm_pc_uses_the_faster_model(self) -> None:
        plan = recommend(profile(native_arm64=True, logical_cpus=18, memory_gb=24.0))

        self.assertEqual(plan.model, "base.en")
        self.assertIn("ARM64", plan.reason)

    def test_light_cpu_uses_the_faster_model(self) -> None:
        self.assertEqual(recommend(profile(logical_cpus=4, memory_gb=8.0)).model, "base.en")

    def test_manual_choice_overrides_automatic(self) -> None:
        plan = resolve("small.en", profile(native_arm64=True))

        self.assertEqual((plan.model, plan.device), ("small.en", "cpu"))

    def test_manual_choice_uses_gpu_when_available(self) -> None:
        plan = resolve("base.en", profile(cuda_ready=True))

        self.assertEqual((plan.device, plan.compute_type), ("cuda", "float16"))
        self.assertEqual(plan.fallback.model, "base.en")

    def test_unknown_choice_is_treated_as_automatic(self) -> None:
        self.assertEqual(resolve("mystery", profile()).model, "small.en")



class CpuThreadTests(unittest.TestCase):
    def test_uses_half_the_cpus_within_safe_bounds(self) -> None:
        self.assertEqual(profile(logical_cpus=4).cpu_threads, 4)
        self.assertEqual(profile(logical_cpus=12).cpu_threads, 6)
        self.assertEqual(profile(logical_cpus=18).cpu_threads, 8)
        self.assertEqual(profile(logical_cpus=24).cpu_threads, 8)


class CommandLineOverrideTests(unittest.TestCase):
    def test_settings_choice_is_used_without_an_override(self) -> None:
        from wordwright.app import plan_from_config
        from wordwright.config import AppConfig

        plan = plan_from_config(AppConfig(), "base.en", profile())
        self.assertEqual(plan.model, "base.en")

    def test_command_line_model_wins_and_keeps_a_cpu_fallback_on_gpu(self) -> None:
        from wordwright.app import plan_from_config
        from wordwright.config import AppConfig

        plan = plan_from_config(AppConfig(model="medium.en"), "auto", profile(cuda_ready=True))
        self.assertEqual((plan.model, plan.device, plan.compute_type), ("medium.en", "cuda", "float16"))
        self.assertEqual(plan.fallback.device, "cpu")

        cpu = plan_from_config(AppConfig(model="medium.en", device="cpu"), "auto", profile(cuda_ready=True))
        self.assertEqual((cpu.device, cpu.compute_type, cpu.fallback), ("cpu", "int8", None))


if __name__ == "__main__":
    unittest.main()
