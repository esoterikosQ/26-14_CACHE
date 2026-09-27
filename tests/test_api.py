import importlib.util
import unittest

import phdq_blt_cache


class PackageAPITests(unittest.TestCase):
    def test_frontier_import_does_not_require_torch(self):
        self.assertEqual(phdq_blt_cache.patch_starts([1, 2], input_length=2), [0, 1])
        self.assertIn("GlobalPrefixReuse", phdq_blt_cache.__all__)

    @unittest.skipUnless(importlib.util.find_spec("torch"), "torch is installed on GPU hosts")
    def test_reuse_api_rejects_training_and_invalid_guard(self):
        import torch
        from phdq_blt_cache import GlobalPrefixReuse

        class Model:
            training = True

        cache = GlobalPrefixReuse(Model())
        with self.assertRaises(ValueError):
            cache.run(torch.tensor([[1, 4]]))
        Model.training = False
        with torch.inference_mode():
            with self.assertRaises(ValueError):
                cache.run(torch.tensor([[1, 4]]), logits_to_keep=1, guard_margin=0)


if __name__ == "__main__":
    unittest.main()
