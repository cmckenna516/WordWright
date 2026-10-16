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
    parser.add_argument(
        "--model",
        default=None,
        help="Override the speech model (default: the Settings choice, Automatic unless changed)",
    )
    parser.add_argument("--device", default=None, choices=("cpu", "cuda"))
    parser.add_argument("--compute-type", default=None)
    parser.add_argument("--microphone", type=int, default=None)
    parser.add_argument("--model-dir", type=Path, default=None)
    parser.add_argument("--list-microphones", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--startup",
        action="store_true",
        help="Start with only the compact overlay visible (used at Windows sign-in)",
    )
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
        if not args.startup and not SingleInstance.request_show():
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
        controller, status = build_app(
            config,
            start_minimized=args.startup,
            show_requested=instance.consume_show_request,
        )
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

