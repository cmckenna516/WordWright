from __future__ import annotations

import unittest

from wordwright.output import DeliveryResult, TextInserter, _is_probable_text_target


class FakeKeyboard:
    def __init__(self) -> None:
        self.events = []

    def press(self, key) -> None:
        self.events.append(("press", key))

    def release(self, key) -> None:
        self.events.append(("release", key))


class TextInserterTests(unittest.TestCase):
    def test_modern_browser_focus_is_treated_as_a_paste_target(self) -> None:
        self.assertTrue(
            _is_probable_text_target(
                foreground_class="Chrome_WidgetWin_1",
                focused_class="Chrome_RenderWidgetHostHWND",
                caret_visible=False,
                owns_foreground=False,
            )
        )

    def test_wordwright_and_desktop_surfaces_are_not_paste_targets(self) -> None:
        self.assertFalse(
            _is_probable_text_target(
                foreground_class="TkTopLevel",
                focused_class="Button",
                caret_visible=False,
                owns_foreground=True,
            )
        )
        self.assertFalse(
            _is_probable_text_target(
                foreground_class="Progman",
                focused_class="SysListView32",
                caret_visible=False,
                owns_foreground=False,
            )
        )

    def test_unknown_focused_app_control_is_allowed(self) -> None:
        self.assertTrue(
            _is_probable_text_target(
                foreground_class="CustomApplicationWindow",
                focused_class="CustomDocumentSurface",
                caret_visible=False,
                owns_foreground=False,
            )
        )

    def test_copies_then_pastes_without_enter(self) -> None:
        copied = []
        slept = []
        keyboard = FakeKeyboard()
        inserter = TextInserter(
            paste_delay_seconds=0.2,
            copy_function=copied.append,
            keyboard_controller=keyboard,
            ctrl_key="CTRL",
            sleep_function=slept.append,
            text_target_detector=lambda: True,
        )

        result = inserter.deliver("A dictated sentence.")

        self.assertEqual(copied, ["A dictated sentence."])
        self.assertEqual(slept, [0.2])
        self.assertEqual(
            keyboard.events,
            [
                ("press", "CTRL"),
                ("press", "v"),
                ("release", "v"),
                ("release", "CTRL"),
            ],
        )
        self.assertNotIn(("press", "enter"), keyboard.events)
        self.assertEqual(result, DeliveryResult.PASTED)

    def test_keeps_text_on_clipboard_when_no_text_target_is_focused(self) -> None:
        copied = []
        keyboard = FakeKeyboard()
        inserter = TextInserter(
            copy_function=copied.append,
            keyboard_controller=keyboard,
            ctrl_key="CTRL",
            sleep_function=lambda seconds: None,
            text_target_detector=lambda: False,
        )

        result = inserter.deliver("Clipboard fallback")

        self.assertEqual(result, DeliveryResult.CLIPBOARD)
        self.assertEqual(copied, ["Clipboard fallback"])
        self.assertEqual(keyboard.events, [])

    def test_rejects_empty_transcript(self) -> None:
        inserter = TextInserter(
            copy_function=lambda value: None,
            keyboard_controller=FakeKeyboard(),
            ctrl_key="CTRL",
            sleep_function=lambda seconds: None,
            text_target_detector=lambda: True,
        )
        with self.assertRaises(ValueError):
            inserter.deliver("")

    def test_retries_a_temporarily_locked_clipboard(self) -> None:
        attempts = []
        sleeps = []

        def flaky_copy(value: str) -> None:
            attempts.append(value)
            if len(attempts) < 3:
                raise OSError("clipboard busy")

        inserter = TextInserter(
            copy_function=flaky_copy,
            keyboard_controller=FakeKeyboard(),
            ctrl_key="CTRL",
            sleep_function=sleeps.append,
            text_target_detector=lambda: True,
        )
        inserter.deliver("Recovered text")

        self.assertEqual(attempts, ["Recovered text"] * 3)
        self.assertEqual(sleeps, [0.05, 0.05, 0.15])


if __name__ == "__main__":
    unittest.main()
