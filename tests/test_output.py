from __future__ import annotations

import ctypes
import os
import unittest

from wordwright.output import (
    DeliveryResult,
    TextInserter,
    _Input,
    _is_probable_text_target,
    chunk_units,
    prepare_for_typing,
    utf16_units,
)


def make_inserter(**overrides):
    typed: list[str] = []
    copied: list[str] = []
    slept: list[float] = []
    options = dict(
        typing_delay_seconds=0.2,
        type_function=typed.append,
        copy_function=copied.append,
        sleep_function=slept.append,
        text_target_detector=lambda: True,
        modifier_detector=lambda: False,
    )
    options.update(overrides)
    return TextInserter(**options), typed, copied, slept


class TextTargetTests(unittest.TestCase):
    def test_modern_browser_focus_is_treated_as_a_text_target(self) -> None:
        self.assertTrue(
            _is_probable_text_target(
                foreground_class="Chrome_WidgetWin_1",
                focused_class="Chrome_RenderWidgetHostHWND",
                caret_visible=False,
                owns_foreground=False,
            )
        )

    def test_wordwright_and_desktop_surfaces_are_not_text_targets(self) -> None:
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


class TextInserterTests(unittest.TestCase):
    def test_types_text_without_touching_the_clipboard(self) -> None:
        inserter, typed, copied, slept = make_inserter()

        result = inserter.deliver("A dictated sentence.")

        self.assertEqual(result, DeliveryResult.TYPED)
        self.assertEqual(typed, ["A dictated sentence."])
        self.assertEqual(copied, [])
        self.assertEqual(slept, [0.2])

    def test_line_breaks_and_tabs_never_reach_the_app(self) -> None:
        inserter, typed, _, _ = make_inserter()

        inserter.deliver("First line\nsecond\r\nline\tend\n")

        self.assertEqual(typed, ["First line second line end"])
        self.assertNotIn("\n", typed[0])

    def test_waits_for_the_hotkey_modifiers_to_be_released(self) -> None:
        held = iter([True, True, False])
        inserter, typed, _, slept = make_inserter(modifier_detector=lambda: next(held))

        inserter.deliver("Hello")

        self.assertEqual(slept, [0.02, 0.02, 0.2])
        self.assertEqual(typed, ["Hello"])

    def test_modifier_wait_gives_up_after_the_limit(self) -> None:
        inserter, typed, _, slept = make_inserter(
            modifier_detector=lambda: True, modifier_wait_seconds=0.1
        )

        inserter.deliver("Hello")

        self.assertLessEqual(len(slept), 7)
        self.assertEqual(typed, ["Hello"])

    def test_uses_clipboard_only_when_no_text_target_is_focused(self) -> None:
        inserter, typed, copied, _ = make_inserter(text_target_detector=lambda: False)

        result = inserter.deliver("Clipboard fallback")

        self.assertEqual(result, DeliveryResult.CLIPBOARD)
        self.assertEqual(copied, ["Clipboard fallback"])
        self.assertEqual(typed, [])

    def test_no_clipboard_when_the_caller_already_saved_it(self) -> None:
        inserter, typed, copied, _ = make_inserter(text_target_detector=lambda: False)

        result = inserter.deliver("Saved elsewhere", clipboard_fallback=False)

        self.assertEqual(result, DeliveryResult.NOT_TYPED)
        self.assertEqual((typed, copied), ([], []))

    def test_blocked_typing_falls_back_to_the_clipboard(self) -> None:
        def blocked(text: str) -> None:
            raise OSError(5, "blocked")

        inserter, _, copied, _ = make_inserter(type_function=blocked)

        result = inserter.deliver("Do not lose me")

        self.assertEqual(result, DeliveryResult.CLIPBOARD)
        self.assertEqual(copied, ["Do not lose me"])

    def test_rejects_empty_transcript(self) -> None:
        inserter, _, _, _ = make_inserter()
        with self.assertRaises(ValueError):
            inserter.deliver("  \n ")

    def test_retries_a_temporarily_locked_clipboard(self) -> None:
        attempts = []

        def flaky_copy(value: str) -> None:
            attempts.append(value)
            if len(attempts) < 3:
                raise OSError("clipboard busy")

        inserter, _, _, slept = make_inserter(
            copy_function=flaky_copy, text_target_detector=lambda: False
        )
        inserter.deliver("Recovered text")

        self.assertEqual(attempts, ["Recovered text"] * 3)
        self.assertEqual(slept, [0.05, 0.05])


class UnicodeTypingTests(unittest.TestCase):
    def test_prepare_for_typing_collapses_whitespace(self) -> None:
        self.assertEqual(prepare_for_typing("  a \n\n b\t c "), "a b c")

    def test_emoji_become_surrogate_pairs(self) -> None:
        self.assertEqual(utf16_units("a😀"), [0x61, 0xD83D, 0xDE00])

    def test_chunks_never_split_a_surrogate_pair(self) -> None:
        units = utf16_units("ab😀cd")
        chunks = chunk_units(units, 3)

        self.assertEqual(chunks[0], [0x61, 0x62, 0xD83D, 0xDE00])
        self.assertEqual(sum(chunks, []), units)

    @unittest.skipUnless(
        os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
        "INPUT layout is checked against 64-bit Windows",
    )
    def test_input_structure_matches_windows_layout(self) -> None:
        # SendInput rejects every event when this size is wrong.
        self.assertEqual(ctypes.sizeof(_Input), 40)


if __name__ == "__main__":
    unittest.main()
