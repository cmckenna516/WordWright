from __future__ import annotations

import logging

from .audio import AudioRecorder
from .config import AppConfig
from .controller import AppController
from .hardware import HardwareProfile, ModelPlan, detect_hardware, resolve
from .hotkeys import GlobalHotkey
from .output import TextInserter
from .settings import SettingsStore
from .status import TrayStatus
from .transcription import LocalTranscriber

LOGGER = logging.getLogger(__name__)


def plan_from_config(config: AppConfig, choice: str, profile: HardwareProfile) -> ModelPlan:
    """Command-line overrides win; otherwise use the Settings choice."""

    if config.model is None:
        return resolve(choice, profile)
    device = config.device or ("cuda" if profile.cuda_ready else "cpu")
    compute_type = config.compute_type or ("float16" if device == "cuda" else "int8")
    fallback = ModelPlan(config.model, "cpu", "int8", "CPU fallback")
    return ModelPlan(
        config.model, device, compute_type, "Command-line override",
        fallback=fallback if device == "cuda" else None,
    )


def _fallback_pair(plan: ModelPlan) -> tuple[str, str] | None:
    if plan.fallback is None:
        return None
    return plan.fallback.model, plan.fallback.compute_type


def build_app(
    config: AppConfig,
    settings: SettingsStore | None = None,
    profile: HardwareProfile | None = None,
) -> tuple[AppController, TrayStatus]:
    settings = settings or SettingsStore()
    profile = profile or detect_hardware()
    plan = plan_from_config(config, settings.snapshot().model_choice, profile)
    LOGGER.info("Speech model: %s (%s)", plan.label, plan.reason)

    status = TrayStatus(settings)
    recorder = AudioRecorder(
        sample_rate=config.sample_rate,
        device=config.microphone,
    )
    transcriber = LocalTranscriber(
        model_name=plan.model,
        device=plan.device,
        compute_type=plan.compute_type,
        download_root=config.model_directory,
        vocabulary_provider=lambda: settings.snapshot().vocabulary,
        cpu_fallback=_fallback_pair(plan),
        cpu_threads=profile.cpu_threads,
    )

    inserter = TextInserter(typing_delay_seconds=config.typing_delay_seconds)
    controller = AppController(
        config=config,
        recorder=recorder,
        transcriber=transcriber,
        inserter=inserter,
        status=status,
    )
    hotkey = GlobalHotkey(
        {
            config.hotkey: controller.handle_hotkey,
            config.cancel_hotkey: controller.cancel_recording,
        }
    )
    controller.attach_hotkey(hotkey)

    def apply_model_setting() -> None:
        new_plan = resolve(settings.snapshot().model_choice, profile)
        LOGGER.info("Switching speech model: %s (%s)", new_plan.label, new_plan.reason)
        controller.reload_model(
            lambda: transcriber.configure(
                new_plan.model,
                new_plan.device,
                new_plan.compute_type,
                _fallback_pair(new_plan),
            )
        )

    status.set_quit_callback(controller.shutdown)
    status.set_toggle_callback(controller.handle_hotkey)
    status.set_model_change_callback(apply_model_setting)
    status.set_model_explainer(
        lambda: _describe_choice(settings.snapshot().model_choice, profile)
    )
    return controller, status


def _describe_choice(choice: str, profile: HardwareProfile) -> str:
    plan = resolve(choice, profile)
    return f"This PC: {profile.describe()}. Uses {plan.label} — {plan.reason}."
