import unittest

from billing import billed_minutes


class BillingContract(unittest.TestCase):
    def test_started_minutes(self):
        # Oracle comes from the accepted billing policy, not a second copy of
        # the implementation's formula. Each boundary distinguishes a defect.
        for seconds, expected in [(0, 0), (1, 1), (59, 1), (60, 1), (61, 2), (120, 2)]:
            with self.subTest(seconds=seconds):
                self.assertEqual(billed_minutes(seconds), expected)

    def test_invalid_input(self):
        for seconds in [-1, 1.5, True, "60"]:
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    billed_minutes(seconds)
