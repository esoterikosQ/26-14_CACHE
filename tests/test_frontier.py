import unittest

from phdq_blt_cache import patch_starts, shared_closed_patch_count


class FrontierTests(unittest.TestCase):
    def test_virtual_next_token_slot_and_padding(self):
        self.assertEqual(patch_starts([1, 3, 2, 0], input_length=5), [0, 1, 4])
        with self.assertRaises(ValueError):
            patch_starts([1, 3, 1], input_length=5)
        with self.assertRaises(ValueError):
            patch_starts([1, 0, 5], input_length=5)

    def test_closed_prefix_excludes_open_or_changed_patch(self):
        self.assertEqual(shared_closed_patch_count([0, 5, 10], [0, 5, 10, 14]), 2)
        self.assertEqual(shared_closed_patch_count([0, 5, 10], [0, 5, 11]), 1)
        self.assertEqual(shared_closed_patch_count([0, 5, 10], [0, 6, 10]), 0)
        with self.assertRaises(ValueError):
            shared_closed_patch_count([0, 5, 5], [0, 5, 6])


if __name__ == "__main__":
    unittest.main()
