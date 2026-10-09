from __future__ import annotations

import unittest
from unittest.mock import patch

from wordwright.single_instance import SingleInstance


class SingleInstanceTests(unittest.TestCase):
    def test_non_windows_instance_is_a_no_op(self) -> None:
        with patch("wordwright.single_instance.os.name", "posix"):
            instance = SingleInstance.acquire()

        self.assertIsNotNone(instance)
        instance.release()


if __name__ == "__main__":
    unittest.main()

