from __future__ import annotations

import os
import unittest
import uuid
from unittest.mock import patch

from wordwright.single_instance import SingleInstance


class SingleInstanceTests(unittest.TestCase):
    def test_non_windows_instance_is_a_no_op(self) -> None:
        with patch("wordwright.single_instance.os.name", "posix"):
            instance = SingleInstance.acquire()

        self.assertIsNotNone(instance)
        instance.release()

    def test_non_windows_show_request_is_a_no_op(self) -> None:
        with patch("wordwright.single_instance.os.name", "posix"):
            self.assertFalse(SingleInstance.request_show())

    def test_non_windows_instance_has_no_pending_show_request(self) -> None:
        instance = SingleInstance()

        self.assertFalse(instance.consume_show_request())

    @unittest.skipUnless(os.name == "nt", "Windows named-event test")
    def test_real_windows_show_request_round_trip(self) -> None:
        suffix = uuid.uuid4()
        with (
            patch("wordwright.single_instance.MUTEX_NAME", f"Local\\WordwrightTestMutex-{suffix}"),
            patch("wordwright.single_instance.SHOW_EVENT_NAME", f"Local\\WordwrightTestShow-{suffix}"),
        ):
            instance = SingleInstance.acquire()
            self.assertIsNotNone(instance)
            try:
                self.assertFalse(instance.consume_show_request())
                self.assertTrue(SingleInstance.request_show())
                self.assertTrue(instance.consume_show_request())
                self.assertFalse(instance.consume_show_request())
            finally:
                instance.release()


if __name__ == "__main__":
    unittest.main()

