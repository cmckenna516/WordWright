from __future__ import annotations

from .audio import AudioRecorder
from .config import AppConfig
from .controller import AppController
from .hotkeys import GlobalHotkey
from .output import TextInserter
from .settings import SettingsStore
from .status import TrayStatus
from .transcription import LocalTranscriber


def build_app(config: AppConfig) -> tuple[AppController, TrayStatus]:
    settings = SettingsStore()
    status = TrayStatus(settings)
    recorder = AudioRecorder(
        sample_rate=config.sample_rate,
        device=config.microphone,
    )
    transcriber = LocalTranscriber(
        model_name=config.model,
        device=config.device,
        compute_type=config.compute_type,
        download_root=config.model_directory,
    )

    inserter = TextInserter(paste_delay_seconds=config.paste_delay_seconds)
    controller = AppController(
        config=config,
        recorder=recorder,
        transcriber=transcriber,
        inserter=inserter,
        status=status,
    )
    hotkey = GlobalHotkey(config.hotkey, controller.handle_hotkey)
    controller.attach_hotkey(hotkey)
    status.set_quit_callback(controller.shutdown)
    status.set_toggle_callback(controller.handle_hotkey)
    return controller, status

