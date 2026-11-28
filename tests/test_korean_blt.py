import math
import unittest

from scripts.compare_korean_blt import paired_bpb, patch_statistics, ratio_summary, select_timing_inputs


def document(original, python, cpp, utf8_bytes):
    return {"utf8_bytes": utf8_bytes, "modes": {"original": {"nll_nats": original}, "count_python": {"nll_nats": python},
                                                "count_cpp": {"nll_nats": cpp}}}


class KoreanComparisonTests(unittest.TestCase):
    def test_paired_bpb_is_byte_weighted_and_reports_no_criterion(self):
        documents = [document(100., 110., 110., 200), document(50., 52., 52., 100), document(80., 79., 79., 150)]
        summary = paired_bpb(documents, replicates=500, seed=3)
        denominator = 450 * math.log(2)
        self.assertAlmostEqual(summary["bpb"]["original"], 230 / denominator)
        self.assertAlmostEqual(summary["bpb"]["count_cpp"], 241 / denominator)
        self.assertAlmostEqual(summary["delta_bpb_count_minus_original"], 11 / denominator)
        lower, upper = summary["paired_document_bootstrap95"]
        self.assertLessEqual(lower, upper)
        self.assertEqual(summary["scored_bytes"], 450)
        self.assertFalse(any("criterion" in key or "passed" in key for key in summary))
        self.assertEqual(summary, paired_bpb(documents, replicates=500, seed=3))
        with self.assertRaises(ValueError):
            paired_bpb(documents[:1])
        with self.assertRaises(ValueError):
            paired_bpb([document(1., 1., 1., 0), document(1., 1., 1., 5)])

    def test_patch_statistics_use_patch_counts(self):
        self.assertEqual(patch_statistics({2: 3, 5: 1}),
                         {"patches": 4, "mean_patch_length": 2.75, "histogram": {"2": 3, "5": 1}})
        with self.assertRaises(ValueError):
            patch_statistics({})

    def test_timing_inputs_take_first_eligible_first_chunk(self):
        documents = [({"document_id": "a"}, [[1] + [5] * 99]), ({"document_id": "b"}, [[1] + [6] * 299, [1] + [6] * 10]),
                     ({"document_id": "c"}, [[1] + [7] * 599])]
        selected = select_timing_inputs(documents, (64, 256, 512))
        self.assertEqual([metadata["document_id"] for metadata, _ in selected], ["a", "b", "c"])
        self.assertEqual([len(ids) for _, ids in selected], [64, 256, 512])
        self.assertEqual(selected[1][1][:2], [1, 6])
        with self.assertRaisesRegex(ValueError, "1024"):
            select_timing_inputs(documents, (1024,))

    def test_ratio_summary_is_baseline_over_candidate(self):
        summary = ratio_summary([2., 2.2, 1.8, 2.], [1., 1.1, .9, 1.], replicates=200, seed=1)
        self.assertAlmostEqual(summary["median_ratio"], 2.)
        lower, upper = summary["paired_bootstrap95"]
        self.assertLessEqual(lower, 2.)
        self.assertGreaterEqual(upper, 2.)
        with self.assertRaises(ValueError):
            ratio_summary([1., 2.], [1.])
        with self.assertRaises(ValueError):
            ratio_summary([1., 0.], [1., 1.])


if __name__ == "__main__":
    unittest.main()
