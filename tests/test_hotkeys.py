from __future__ import annotations

import os
import queue
import threading
import unittest

from wordwright import hotkeys
from wordwright.hotkeys import (
    HoldKeyListener,
    WindowsHotkeys,
    hold_hotkey_label,
    hotkey_label,
    parse_hold_hotkey,
    parse_hotkey,
    shortcut_conflict,
)


class FakeUser32:
    """Stands in for user32 so the Windows message loop can be tested anywhere."""

    def __init__(self, taken: set[tuple[int, int]] | None = None) -> None:
        self.messages: queue.Queue[tuple[int, int]] = queue.Queue()
        self.registered: dict[int, tuple[int, int]] = {}
        self.taken = taken or set()
        self.changed = threading.Event()
        self.last_error = 0

    def RegisterHotKey(self, hwnd, identifier, modifiers, virtual_key) -> int:
        if (modifiers & ~0x4000, virtual_key) in self.taken:
            self.last_error = 1409
            return 0
        self.registered[identifier] = (modifiers, virtual_key)
        self.changed.set()
        return 1

    def UnregisterHotKey(self, hwnd, identifier) -> int:
        self.registered.pop(identifier, None)
        self.changed.set()
        return 1

    def PeekMessageW(self, *args) -> int:
        return 0

    def PostThreadMessageW(self, thread_id, message, wparam, lparam) -> int:
        self.messages.put((message, wparam))
        return 1

    def GetMessageW(self, pointer, *args) -> int:
        message, wparam = self.messages.get(timeout=5)
        target = pointer._obj
        target.message = message
        target.wParam = wparam
        return 0 if message == hotkeys._WM_QUIT else 1


class FakeKernel32:
    def GetCurrentThreadId(self) -> int:
        return 7


def wait_for(condition, timeout: float = 2.0) -> bool:
    event = threading.Event()
    for _ in range(int(timeout / 0.01)):
        if condition():
            return True
        event.wait(0.01)
    return condition()


class ParseHotkeyTests(unittest.TestCase):
    def test_default_shortcut(self) -> None:
        hotkey = parse_hotkey("ctrl+shift+space")
        self.assertEqual(hotkey.label, "Ctrl+Shift+Space")
        self.assertEqual(hotkey.virtual_key, 0x20)
        self.assertEqual(hotkey.windows_modifiers, 0x4000 | 0x0002 | 0x0004)

    def test_order_and_case_are_normalized(self) -> None:
        self.assertEqual(parse_hotkey("Alt + CTRL + k").spec, "ctrl+alt+k")
        self.assertEqual(parse_hotkey("ctrl+shift+f9").label, "Ctrl+Shift+F9")
        self.assertEqual(parse_hotkey("ctrl+shift+f9").virtual_key, 0x78)

    def test_single_keys_and_shift_only_are_rejected(self) -> None:
        for spec in ("space", "ctrl", "ctrl+alt", "shift+k", "ctrl+alt+space+k", "ctrl+alt+enter"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                parse_hotkey(spec)

    def test_invalid_saved_value_falls_back_to_default_label(self) -> None:
        self.assertEqual(hotkey_label("space"), "Ctrl+Shift+Space")

    def test_hold_shortcut_can_be_modifiers_only(self) -> None:
        hold = parse_hold_hotkey("Alt + CTRL")
        self.assertEqual(hold.spec, "ctrl+alt")
        self.assertEqual(hold.label, "Ctrl+Alt")
        self.assertEqual(hold_hotkey_label("bad"), "Ctrl+Alt")

    def test_hold_shortcut_can_include_a_main_key(self) -> None:
        hold = parse_hold_hotkey("ctrl+alt+d")
        self.assertEqual(hold.key, "d")
        self.assertEqual(hold.label, "Ctrl+Alt+D")

    def test_hold_shortcut_requires_two_modifiers(self) -> None:
        for spec in ("ctrl", "ctrl+d", "shift"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                parse_hold_hotkey(spec)

    def test_overlap_with_modifier_only_hold_is_rejected(self) -> None:
        conflict = shortcut_conflict(
            parse_hotkey("ctrl+alt+space"),
            parse_hold_hotkey("ctrl+alt"),
        )
        self.assertIn("overlaps", conflict)
        self.assertIsNone(
            shortcut_conflict(
                parse_hotkey("ctrl+shift+space"),
                parse_hold_hotkey("ctrl+alt"),
            )
        )


class FakeHoldListener:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.spec = "ctrl+alt"

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def join(self, timeout=None) -> None:
        del timeout

    def set_hotkey(self, spec: str) -> str | None:
        self.spec = spec
        return None


class FakeKeyboardListener:
    def __init__(self, **callbacks) -> None:
        self.on_press = callbacks["on_press"]
        self.on_release = callbacks["on_release"]
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def join(self, timeout=None) -> None:
        del timeout


class HoldKeyListenerTests(unittest.TestCase):
    def make(self, spec="ctrl+alt"):
        events = []
        listener = HoldKeyListener(
            spec,
            lambda: events.append("start"),
            lambda: events.append("stop"),
            listener_factory=FakeKeyboardListener,
            key_state=lambda key: True,
        )
        listener.start()
        self.addCleanup(listener.stop)
        return listener, listener._listener, events

    def test_modifier_hold_starts_once_and_stops_on_either_release(self) -> None:
        _, keyboard, events = self.make()
        keyboard.on_press("ctrl_l")
        keyboard.on_press("alt_r")
        keyboard.on_press("alt_r")
        self.assertEqual(events, ["start"])

        keyboard.on_release("ctrl_l")
        self.assertEqual(events, ["start", "stop"])

    def test_optional_main_key_must_also_be_held(self) -> None:
        _, keyboard, events = self.make("ctrl+alt+d")
        keyboard.on_press("ctrl")
        keyboard.on_press("alt")
        self.assertEqual(events, [])
        keyboard.on_press("d")
        self.assertEqual(events, ["start"])
        keyboard.on_release("d")
        self.assertEqual(events, ["start", "stop"])

    def test_watchdog_stops_if_a_release_event_is_missed(self) -> None:
        down = {0x11: True, 0x12: True}
        events = []
        listener = HoldKeyListener(
            "ctrl+alt",
            lambda: events.append("start"),
            lambda: events.append("stop"),
            listener_factory=FakeKeyboardListener,
            key_state=lambda key: down.get(key, False),
        )
        listener.start()
        self.addCleanup(listener.stop)
        keyboard = listener._listener
        keyboard.on_press("ctrl")
        keyboard.on_press("alt")
        self.assertEqual(events, ["start"])

        down[0x12] = False
        self.assertTrue(wait_for(lambda: events == ["start", "stop"]))


class WindowsHotkeysTests(unittest.TestCase):
    def make(self, taken=None):
        user32 = FakeUser32(taken)
        toggles, cancels = threading.Event(), threading.Event()
        hold = FakeHoldListener()
        listener = WindowsHotkeys(
            "ctrl+shift+space",
            on_toggle=toggles.set,
            on_cancel=cancels.set,
            user32=user32,
            kernel32=FakeKernel32(),
            get_last_error=lambda: user32.last_error,
            hold_listener=hold,
        )
        listener.start()
        self.addCleanup(listener.join, 1.0)
        self.addCleanup(listener.stop)
        return listener, user32, toggles, cancels

    def test_registers_the_exact_combination_with_windows(self) -> None:
        listener, user32, toggles, _ = self.make()

        self.assertIsNone(listener.registration_error)
        self.assertEqual(user32.registered[1], (0x4000 | 0x0006, 0x20))
        user32.messages.put((hotkeys._WM_HOTKEY, 1))
        self.assertTrue(toggles.wait(2))

    def test_escape_is_claimed_only_while_recording(self) -> None:
        listener, user32, _, cancels = self.make()
        self.assertNotIn(2, user32.registered)

        listener.set_cancel_enabled(True)
        self.assertTrue(wait_for(lambda: 2 in user32.registered))
        self.assertEqual(user32.registered[2], (0x4000, 0x1B))
        user32.messages.put((hotkeys._WM_HOTKEY, 2))
        self.assertTrue(cancels.wait(2))

        listener.set_cancel_enabled(False)
        self.assertTrue(wait_for(lambda: 2 not in user32.registered))

    def test_shortcut_taken_by_another_app_is_reported(self) -> None:
        listener, _, _, _ = self.make(taken={(0x0006, 0x20)})

        self.assertIn("already used", listener.registration_error)

    def test_changing_the_shortcut_swaps_the_registration(self) -> None:
        listener, user32, _, _ = self.make()

        self.assertIsNone(listener.set_hotkey("ctrl+shift+d"))
        self.assertEqual(user32.registered[1], (0x4000 | 0x0006, ord("D")))
        self.assertEqual(listener.label, "Ctrl+Shift+D")

    def test_a_taken_new_shortcut_keeps_the_old_one(self) -> None:
        listener, user32, _, _ = self.make(taken={(0x0006, ord("D"))})

        error = listener.set_hotkey("ctrl+shift+d")

        self.assertIn("already used", error)
        self.assertEqual(user32.registered[1], (0x4000 | 0x0006, 0x20))
        self.assertEqual(listener.label, "Ctrl+Shift+Space")

    def test_invalid_shortcut_is_rejected_before_windows_sees_it(self) -> None:
        listener, user32, _, _ = self.make()

        self.assertIn("Ctrl, Alt, or Win", listener.set_hotkey("shift+k"))
        self.assertEqual(user32.registered[1][1], 0x20)

    def test_overlapping_toggle_is_rejected(self) -> None:
        listener, user32, _, _ = self.make()
        error = listener.set_hotkey("ctrl+alt+space")
        self.assertIn("overlaps", error)
        self.assertEqual(user32.registered[1], (0x4000 | 0x0006, 0x20))

    def test_hold_shortcut_can_be_changed_independently(self) -> None:
        listener, _, _, _ = self.make()
        self.assertIsNone(listener.set_hold_hotkey("win+alt"))
        self.assertEqual(listener.hold_label, "Alt+Win")



class BrokenUser32(FakeUser32):
    def PeekMessageW(self, *args) -> int:
        raise OSError("no message queue")


class ListenerStartupTests(unittest.TestCase):
    def test_a_crashing_listener_reports_instead_of_hanging(self) -> None:
        listener = WindowsHotkeys(
            "ctrl+shift+space", lambda: None, lambda: None,
            user32=BrokenUser32(), kernel32=FakeKernel32(), get_last_error=lambda: 0,
            hold_listener=FakeHoldListener(),
        )
        listener.start()
        self.assertIn("could not be set up", listener.registration_error)

    @unittest.skipUnless(os.name == "nt", "Uses the real Windows API")
    def test_real_windows_api_round_trip(self) -> None:
        listener = WindowsHotkeys(
            "ctrl+shift+f12",
            lambda: None,
            lambda: None,
            hold_listener=FakeHoldListener(),
        )
        listener.start()
        try:
            # A CI desktop may refuse hotkeys; what matters is that every
            # Windows call is wired correctly rather than crashing.
            self.assertNotIn("could not be set up", listener.registration_error or "")
            listener.set_cancel_enabled(True)
            listener.set_cancel_enabled(False)
            result = listener.set_hotkey("ctrl+shift+f11")
            self.assertNotEqual(result, "Windows did not respond while changing the shortcut.")
        finally:
            listener.stop()
            listener.join(2.0)


if __name__ == "__main__":
    unittest.main()
