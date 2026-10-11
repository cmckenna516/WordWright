from __future__ import annotations

import threading
import time
from pathlib import Path

from wordwright.overlay import RecordingOverlay


def main() -> int:
    logo = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "wordwright"
        / "assets"
        / "logo-scroll-v2.png"
    )
    overlay = RecordingOverlay(logo)

    def drive_states() -> None:
        overlay.update("Recording")
        time.sleep(2.0)
        overlay.update("Transcribing")
        time.sleep(2.0)
        overlay.update("Text typed")
        time.sleep(1.0)
        overlay.stop()

    driver = threading.Thread(target=drive_states, daemon=True)
    driver.start()
    completed = overlay.run()
    driver.join(timeout=1.0)
    if not completed:
        print("Overlay smoke test failed. Check the diagnostic log for details.")
        return 1
    print("Overlay smoke test completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
