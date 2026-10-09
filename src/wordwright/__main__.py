from __future__ import annotations

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .app import build_app
from .audio import list_microphones
from .config import AppConfig
from .settings import default_settings_path
from .single_instance import SingleInstance, show_already_running_message


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Windows dictation")
    parser.add_argument("--model", default="small.en", help="Local Whisper model")
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--microphone", type=int, default=None)
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--list-microphones", action="store_true")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args(argv)


def configure_logging(debug: bool) -> Path:
    log_path = default_settings_path().parent / "logs" / "wordwright.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_path,
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        )
    ]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
    return log_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.debug)

    if args.list_microphones:
        microphones = list_microphones()
        if not microphones:
            print("No microphone input devices were found.")
            return 1
        print("\n".join(microphones))
        return 0

    instance = SingleInstance.acquire()
    if instance is None:
        show_already_running_message()
        return 0

    config_options = {
        "model": args.model,
        "device": args.device,
        "compute_type": args.compute_type,
        "microphone": args.microphone,
    }
    if args.model_dir is not None:
        config_options["model_directory"] = args.model_dir
    config = AppConfig(
        **config_options,
    )

    try:
        controller, status = build_app(config)
        try:
            controller.start()
            status.run()
        except KeyboardInterrupt:
            pass
        finally:
            controller.shutdown()
    finally:
        instance.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())

