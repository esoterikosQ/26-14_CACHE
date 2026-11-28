import unittest
from unittest.mock import patch
import os
from pathlib import Path
import tempfile

import numpy as np
import torch

from phdq_blt_cache.blt_patcher import CountPatcherAdapter
from phdq_blt_cache.count_patcher import BoundaryRule, CountConfig, CountTable, decision_patch_lengths, rollout
from scripts.smoke_blt_count_patcher import greedy_generate, sample_generate, timing_summary, validation_prefixes
from scripts.compare_blt_patchers import boundary_comparison, boundary_summary, bpb_summary, evaluation_documents, incremental_prefixes, timed_replay
from scripts.profile_count_patcher import CostMeter, MeasuredInput, instrument, summarize
from scripts.benchmark_cpp_count_patcher import NativeAdapter, build_native
from scripts.diagnose_blt_termination import decoding_plan, eos_statistics, generation_budget, instruction_control_prompts, repetition_metrics, simple_control_prompts
from scripts.diagnose_blt_eos_causes import capture_stages, probe_positions, stage_contexts, tensor_comparison


class BLTPatcherTests(unittest.TestCase):
    def test_native_backend_requires_explicit_library_and_supported_mode(self):
        config, rule = CountConfig(), BoundaryRule((-4., 0., 0., 2., .2), 4.5, .375)
        background = CountTable(config).freeze()
        self.assertEqual(CountPatcherAdapter(config, rule, background).backend, "python")
        for options in ({"backend": "unknown"}, {"backend": "cpp"}, {"native_library": "unused.so"},
                        {"backend": "cpp", "native_library": "missing.so"}):
            with self.assertRaises((ValueError, FileNotFoundError)):
                CountPatcherAdapter(config, rule, background, **options)
        for invalid in (CountTable(config), CountTable(CountConfig(max_context=0)).freeze()):
            with self.assertRaisesRegex(ValueError, "frozen compatible"):
                CountPatcherAdapter(config, rule, invalid, backend="cpp", native_library="unused.so")

    @unittest.skipUnless(os.environ.get("BLT_TEST_NATIVE_CPP") == "1", "Explicit C++ compiler opt-in required")
    def test_native_count_probe_matches_python_numbers_boundaries_and_reset(self):
        config = CountConfig()
        background = CountTable(config)
        background.add_document([1] + list(b"abc abc abc test"))
        background.freeze()
        rule = BoundaryRule((-4.396439611468035, 0., 0., 2.4930392588197363, .22337717045987543), 4.5313422072519485, .375)
        with tempfile.TemporaryDirectory() as directory:
            module, _, library = build_native(directory)
            adapter = NativeAdapter(module, config, rule, background)
            production = CountPatcherAdapter(config, rule, background, backend="cpp", native_library=library)
            with torch.inference_mode():
                for values in ([1, 101], [1] + list(b"abc abc abc test"), [1] + list(b"abc abc abc test!"), [1, 100, 2, 101], [1] + list(range(4, 260))):
                    ids = torch.tensor([values])
                    expected = rollout(values, config=config, rule=rule, background=background)
                    self.assertEqual(adapter.patch_lengths(ids).tolist()[0], decision_patch_lengths(expected))
                    self.assertEqual(production.patch_lengths(ids).tolist()[0], decision_patch_lengths(expected))
                    bounded = production.patch_lengths(ids, max_patch_length=2).tolist()[0]
                    self.assertLessEqual(max(bounded), 2)
                    self.assertEqual(sum(bounded), len(values) + 1)
                    _, diagnostics = module.run(adapter.state, values, True)
                    np.testing.assert_allclose(np.array(diagnostics)[:, :2], [(item.entropy, item.score) for item in expected], rtol=0, atol=2e-13)
                    self.assertEqual([tuple(row[2:]) for row in diagnostics], [(item.repeated_length, item.distance, int(item.boundary)) for item in expected])
                for values in ([1, 3], [1, 260], [1, True]):
                    with self.assertRaises(ValueError):
                        module.run(adapter.state, values)
                production.reset()
                self.assertEqual(production.patch_lengths(torch.tensor([[1, 101]])).tolist()[0],
                                 decision_patch_lengths(rollout([1, 101], config=config, rule=rule, background=background)))

    def test_cost_meter_has_disjoint_categories_and_time_weighted_shares(self):
        ticks = iter((1., 3., 4., 7.))
        meter = CostMeter(lambda: next(ticks))
        self.assertEqual(meter.call("lookup", lambda: 5), 5)
        self.assertEqual(meter.call("transfer", lambda: 6), 6)
        sample = meter.finish(8.)
        self.assertEqual(sample["seconds"], {"lookup": 2., "transfer": 3., "compute_and_other": 3.})
        self.assertEqual(sample["calls"], {"lookup": 1, "transfer": 1})
        summary = summarize([sample, sample])
        self.assertEqual(summary["total_p50_seconds"], 8.)
        self.assertEqual(summary["time_weighted_percent"], {"lookup": 25., "transfer": 37.5, "compute_and_other": 37.5})
        with self.assertRaises(ValueError):
            meter.finish(4.)

    def test_cost_instrumentation_preserves_boundaries_and_restores_functions(self):
        config = CountConfig()
        background = CountTable(config).freeze()
        adapter = CountPatcherAdapter(config, BoundaryRule((-4., 0., 0., 2., .2), 4.5, .375), background)
        original_tensor = torch.tensor
        original_lookup = background.lookup
        with torch.inference_mode(), patch("torch.cuda.synchronize"):
            ids = torch.tensor([[1, 101, 102, 103, 104]])
            expected = adapter.patch_lengths(ids)
            adapter.reset()
            meter = CostMeter()
            with instrument(adapter, meter, torch):
                actual = adapter.patch_lengths(MeasuredInput(ids, meter))
            self.assertTrue(torch.equal(actual, expected))
            self.assertEqual(meter.calls["input_to_cpu"], 1)
            self.assertEqual(meter.calls["output_to_gpu"], 1)
            self.assertEqual(meter.calls["background_lookup"], meter.calls["online_lookup"])
            self.assertIs(torch.tensor, original_tensor)
            self.assertEqual(background.lookup, original_lookup)
            with self.assertRaisesRegex(RuntimeError, "restore"):
                with instrument(adapter, CostMeter(), torch):
                    raise RuntimeError("restore")
            self.assertIs(torch.tensor, original_tensor)
            self.assertEqual(background.lookup, original_lookup)

    def test_total_replay_includes_initial_forward_and_pairs_component_times(self):
        ids = torch.tensor([[1] + list(range(100, 140))])
        priming, extensions = incremental_prefixes(ids)
        events = []
        ticks = iter((10., 12., 44.))

        def forward(current):
            events.append(current.shape[1])
            self.assertTrue(torch.equal(current, ids[:, :current.shape[1]]))

        def synchronize():
            events.append("sync")

        durations = timed_replay(priming, extensions, forward, synchronize, clock=lambda: next(ticks))
        self.assertEqual(events, ["sync", 9, "sync"] + list(range(10, 42)) + ["sync"])
        self.assertEqual(durations, {"model_initial": 2., "model_incremental32": 32., "model_total32": 34.})
        self.assertEqual(durations["model_initial"] + durations["model_incremental32"], durations["model_total32"])

    def test_incremental_replay_uses_identical_bytes_and_excludes_priming(self):
        ids = torch.tensor([[1] + list(range(100, 140))])
        original = ids.clone()
        priming, extensions = incremental_prefixes(ids)
        self.assertEqual(priming.shape, (1, 9))
        self.assertEqual(len(extensions), 32)
        self.assertEqual([current.shape[1] for current in extensions], list(range(10, 42)))
        self.assertTrue(torch.equal(extensions[-1], ids))
        for current in extensions:
            self.assertTrue(torch.equal(current, ids[:, :current.shape[1]]))
            self.assertTrue(torch.equal(current[:, :priming.shape[1]], priming))
        for mode in ("original", "count_lmdb"):
            calls = []
            calls.append(priming.tolist()[0])
            timed_calls = [current.tolist()[0] for current in extensions]
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(timed_calls), 32, mode)
            self.assertEqual([current[-1] for current in timed_calls], ids[0, -32:].tolist())
        self.assertTrue(torch.equal(ids, original))

    def test_incremental_replay_rejects_invalid_steps_and_prefix_shapes(self):
        for steps in (0, -1, True, 1.5, 33):
            with self.assertRaises(ValueError):
                incremental_prefixes(torch.ones((1, 34), dtype=torch.long), steps)
        for shape in ((34,), (2, 34), (1, 33), (1, 1, 34)):
            with self.assertRaises(ValueError):
                incremental_prefixes(torch.ones(shape, dtype=torch.long))
        priming, extensions = incremental_prefixes(torch.ones((1, 34), dtype=torch.long))
        self.assertEqual(priming.shape[1], 2)
        self.assertEqual(len(extensions), 32)

    def test_comparison_boundaries_exclude_forced_starts_and_include_virtual_slot(self):
        counts = boundary_comparison([1, 2, 2], [1, 1, 1, 2], 4)
        self.assertEqual(counts, {"tp": 1, "fp": 1, "fn": 0, "positions": 3})
        self.assertAlmostEqual(boundary_summary(counts)["f1"], 2 / 3)
        self.assertAlmostEqual(boundary_summary(counts)["f0_5"], 5 / 9)
        virtual = boundary_comparison([1, 3, 1], [1, 4], 4)
        self.assertEqual(virtual["fn"], 1)
        for lengths in ([1, 2], [1, 0, 4], [1, 4.]):
            with self.assertRaises(ValueError):
                boundary_comparison(lengths, [1, 4], 4)

    def test_comparison_bpb_uses_paired_byte_weighted_document_bootstrap(self):
        import math

        documents = [{"utf8_bytes": size, "modes": {
            "original": {"nll_nats": size * math.log(2)},
            "count_lmdb": {"nll_nats": size * 2 * math.log(2)}}} for size in (1, 5)]
        summary = bpb_summary(documents)
        self.assertEqual(summary["scored_bytes"], 6)
        self.assertAlmostEqual(summary["original_bpb"], 1)
        self.assertAlmostEqual(summary["count_bpb"], 2)
        np.testing.assert_allclose(summary["paired_document_bootstrap95"], [1, 1])
        self.assertFalse(summary["bpb_criterion_passed"])
        self.assertEqual(summary, bpb_summary(documents))
        with self.assertRaises(ValueError):
            bpb_summary(documents[:1])

    def test_comparison_document_chunks_preserve_bytes_and_validate_hashes(self):
        import hashlib
        import json

        text = "\u00e9" * 1030
        raw = text.encode("utf-8")
        row = {"source": "fixture", "revision": "fixed", "document_id": "one", "text": text,
               "text_sha256": hashlib.sha256(raw).hexdigest()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.jsonl"
            path.write_text(json.dumps(row) + "\n")
            documents = list(evaluation_documents(directory, "test"))
            metadata, chunks = documents[0]
            self.assertEqual(metadata["utf8_bytes"], len(raw))
            self.assertEqual([len(chunk) for chunk in chunks], [2048, 14])
            self.assertEqual(bytes(value - 4 for chunk in chunks for value in chunk[1:]), raw)
            path.write_text(json.dumps({**row, "text_sha256": "bad"}) + "\n")
            with self.assertRaises(ValueError):
                list(evaluation_documents(directory, "test"))
            path.write_text((json.dumps(row) + "\n") * 2)
            with self.assertRaises(ValueError):
                list(evaluation_documents(directory, "test"))

    def test_patcher_sampling_is_seeded_unfiltered_and_masks_special_ids(self):
        inputs = torch.tensor([[1, 100]])

        def forward(ids):
            logits = torch.full((1, 1, 260), -torch.inf)
            logits[..., [0, 1, 3]] = 100
            logits[..., [100, 101]] = 0
            return logits, None

        first = sample_generate(inputs, forward, max_new_tokens=64, seed=42)
        torch.manual_seed(7)
        replay = sample_generate(inputs, forward, max_new_tokens=64, seed=42)
        other = sample_generate(inputs, forward, max_new_tokens=64, seed=20261027)
        self.assertEqual(first, replay)
        self.assertNotEqual(first["generated_ids"], other["generated_ids"])
        self.assertEqual(set(first["generated_ids"]), {100, 101})
        self.assertEqual(first["sampling"], {"do_sample": True, "temperature": 1., "top_p": 1., "top_k": 0, "seed": 42})
        self.assertEqual(greedy_generate(inputs, forward, max_new_tokens=3)["generated_ids"], [100] * 3)

    def test_patcher_sampling_rejects_invalid_seed(self):
        for seed in (-1, True, 2 ** 63, 1.5):
            with self.assertRaises(ValueError):
                sample_generate(torch.tensor([[1, 100]]), None, max_new_tokens=3, seed=seed)

    def test_decoding_plan_fixes_policies_and_seeds_without_penalties(self):
        plan = decoding_plan()
        self.assertEqual(len(plan), 5)
        self.assertEqual(plan[0], {"name": "greedy", "seed": None, "settings": {"do_sample": False}})
        for name, temperature, top_p in (("full_sampling", 1., 1.), ("nucleus_sampling", .8, .9)):
            candidates = [candidate for candidate in plan if candidate["name"] == name]
            self.assertEqual([candidate["seed"] for candidate in candidates], [42, 20261027])
            for candidate in candidates:
                self.assertEqual(candidate["settings"], {"do_sample": True, "temperature": temperature, "top_p": top_p, "top_k": 0})

    def test_repetition_metrics_keep_eos_and_repetition_separate(self):
        result = repetition_metrics([14] * 40 + [2])
        self.assertTrue(result["repetition_flag"])
        self.assertEqual(result["body_byte_count"], 40)
        self.assertEqual(result["trailing_whitespace_ids"], 40)
        self.assertEqual(result["longest_identical_byte_run"], 40)
        self.assertEqual(repetition_metrics([2])["repeat8_fraction"], 0)
        self.assertFalse(repetition_metrics(list(range(50, 90)))["repetition_flag"])
        for invalid in ([], [2, 100], [100, 2, 2], [1, 100], [260]):
            with self.assertRaises(ValueError):
                repetition_metrics(invalid)

    def test_stage_context_selection_is_fixed_and_rejects_input_eos(self):
        names = ("story_letter", "compare_travel", "compare_backup", "story_clock", "compare_laptop")
        source = {"simple_controls": [{"name": name, "input_ids": [1, 100], "modes": {
            mode: {"generated_ids": [101] * 2048} for mode in ("original_hf_default", "count_lmdb")}}
            for name in names]}
        contexts = stage_contexts(source)
        self.assertEqual(len(contexts), 7)
        self.assertEqual([context["position"] for context in contexts], [0, 412, 428, 2047, 655, 1338, 867])
        self.assertTrue(all(2 not in context["input_ids"] for context in contexts))
        source["simple_controls"][1]["modes"]["original_hf_default"]["generated_ids"][0] = 2
        with self.assertRaises(ValueError):
            stage_contexts(source)
        source["simple_controls"][1]["modes"]["original_hf_default"]["generated_ids"] = [101]
        with self.assertRaises(ValueError):
            stage_contexts(source)

    def test_stage_tensor_comparison_distinguishes_shape_and_value(self):
        reference = torch.tensor([1., 2.])
        self.assertTrue(tensor_comparison(reference, reference)["equal"])
        difference = tensor_comparison(reference, reference + 1)
        self.assertFalse(difference["equal"])
        self.assertEqual(difference["max_abs_difference"], 1)
        self.assertEqual(difference["mean_abs_difference"], 1)
        self.assertFalse(tensor_comparison(reference, reference[:1])["same_shape"])

    def test_stage_capture_removes_all_hooks_after_forward_failure(self):
        class FailingEncoder(torch.nn.Module):
            def forward(self, inputs_embeds, attention_mask=None):
                self.observed_mask = attention_mask.detach().clone()
                raise ValueError("Intentional forward failure")

        class FailingModel(torch.nn.Module):
            dtype = torch.float32

            def __init__(self):
                super().__init__()
                self.model = torch.nn.ModuleDict({
                    "patcher": torch.nn.Identity(), "local_encoder": FailingEncoder(),
                    "global_transformer": torch.nn.Identity(), "local_decoder": torch.nn.Identity()})

            def forward(self, input_ids, **kwargs):
                return self.model.local_encoder(inputs_embeds=input_ids.float().unsqueeze(-1))

        model = FailingModel()
        ids = torch.tensor([[1, 100, 101]])
        with self.assertRaisesRegex(ValueError, "Intentional"):
            capture_stages(model, ids, full_local=("local_encoder",))
        mask = model.model.local_encoder.observed_mask[0, 0]
        self.assertTrue(torch.equal(mask.tril(), torch.zeros(3, 3)))
        self.assertEqual(mask[0, 1], torch.finfo(torch.float32).min)
        for module in model.modules():
            self.assertFalse(module._forward_hooks)
            self.assertFalse(module._forward_pre_hooks)

    def test_eos_cause_probes_exclude_eos_and_locate_whitespace_tail(self):
        positions, tail = probe_positions([101, 102] + [14] * 30)
        self.assertEqual(tail, 30)
        self.assertIn(2, positions)
        self.assertIn(18, positions)
        self.assertEqual(max(positions), 31)
        positions, tail = probe_positions([101, 102, 2])
        self.assertEqual(positions, [0, 2])
        self.assertEqual(tail, 0)

    def test_instruction_suite_has_nine_fixed_byte_exact_prompts(self):
        class ByteTokenizer:
            bos_token_id = 1

            def encode(self, text, *, add_special_tokens, truncation):
                if add_special_tokens or truncation:
                    raise ValueError("Unexpected tokenizer options")
                return [byte + 4 for byte in text.encode("utf-8")]

        tokenizer = ByteTokenizer()
        controls = instruction_control_prompts(tokenizer)
        self.assertEqual(len(controls), 9)
        self.assertEqual(len({control["name"] for control in controls}), 9)
        for category in ("story", "process", "comparison"):
            self.assertEqual(sum(control["category"] == category for control in controls), 3)
        for control in controls:
            self.assertEqual(control["input_ids"], [1] + [byte + 4 for byte in control["source_text"].encode("utf-8")])
            self.assertNotIn(2, control["input_ids"])
            self.assertNotIn(3, control["input_ids"])
            self.assertLessEqual(len(control["input_ids"]) + 2048, 4096)
        tokenizer.bos_token_id = 2
        with self.assertRaises(ValueError):
            instruction_control_prompts(tokenizer)

    def test_generation_budget_allows_explicit_increase_without_context_overflow(self):
        self.assertEqual(generation_budget(2048, 2000, 4096, 128), 2048)
        self.assertEqual(generation_budget(None, 100, 4096, 128), 128)
        for invalid in (0, -1, True):
            with self.assertRaises(ValueError):
                generation_budget(invalid, 100, 4096, 128)
        with self.assertRaises(ValueError):
            generation_budget(2048, 2049, 4096, 128)

    def test_simple_controls_preserve_bytes_and_do_not_inject_eos(self):
        class ByteTokenizer:
            bos_token_id = 1

            def encode(self, text, *, add_special_tokens, truncation):
                self_options = (add_special_tokens, truncation)
                if self_options != (False, False):
                    raise ValueError("Unexpected tokenizer options")
                return [byte + 4 for byte in text.encode("utf-8")]

        def encode_prompt(tokenizer, text, *, max_new_bytes):
            self.assertEqual(max_new_bytes, 128)
            return [1] + tokenizer.encode(text + "\n<BLT_GEC_SEP>\n", add_special_tokens=False, truncation=False)

        controls = simple_control_prompts(ByteTokenizer(), encode_prompt)
        self.assertEqual(len(controls), 8)
        self.assertEqual(len({control["name"] for control in controls}), 8)
        for control in controls:
            self.assertEqual(control["input_ids"][0], 1)
            self.assertNotIn(2, control["input_ids"])
            self.assertNotIn(3, control["input_ids"])
            expected = control["source_text"] + ("\n<BLT_GEC_SEP>\n" if control["input_format"] == "gec" else "")
            self.assertEqual(bytes(token - 4 for token in control["input_ids"][1:]).decode("utf-8"), expected)
        with self.assertRaises(ValueError):
            simple_control_prompts(ByteTokenizer(), lambda *args, **kwargs: [1, 2])

    def test_eos_score_diagnostic_does_not_suppress_eos(self):
        logits = torch.zeros(260)
        logits[0] = 100
        logits[2] = 10
        stats = eos_statistics(logits)
        self.assertFalse(stats["eos_suppressed"])
        self.assertEqual(stats["selected_id"], 2)
        self.assertEqual(stats["eos_rank_allowed"], 1)
        self.assertGreater(stats["eos_probability_allowed"], 0.9)
        self.assertLess(stats["eos_probability_raw"], 1e-10)
        logits[100] = 12
        stats = eos_statistics(logits)
        self.assertEqual(stats["selected_id"], 100)
        self.assertEqual(stats["eos_rank_allowed"], 2)
        self.assertEqual(stats["best_minus_eos_logit"], 2)
        with self.assertRaises(ValueError):
            eos_statistics(torch.zeros(259))

    def test_natural_eos_and_generation_cap_are_distinct(self):
        inputs = torch.tensor([[1, 100]])
        calls = []

        def forward(ids):
            calls.append(ids.tolist())
            logits = torch.zeros((1, ids.shape[1], 260))
            logits[0, -1, 0] = 100
            logits[0, -1, 1] = 100
            logits[0, -1, 3] = 100
            logits[0, -1, 2 if ids.shape[1] == 3 else 101] = 10
            return logits, None

        with torch.inference_mode():
            result = greedy_generate(inputs, forward, max_new_tokens=8)
            self.assertEqual(result["generated_ids"], [101, 2])
            self.assertEqual(result["stop_reason"], "eos")
            self.assertEqual(len(calls), 2)
            self.assertEqual(result["text"], "a")
            capped = greedy_generate(inputs, forward, max_new_tokens=1)
            self.assertFalse(capped["eos"])
            self.assertEqual(capped["stop_reason"], "max_new_tokens")
            self.assertEqual(inputs.tolist(), [[1, 100]])
            with self.assertRaises(ValueError):
                greedy_generate(inputs, forward, max_new_tokens=0)
        self.assertEqual(timing_summary([1., 2., 3.])["p50_seconds"], 2.)
        self.assertAlmostEqual(timing_summary([1., 2., 3.])["p95_seconds"], 2.9)

    def test_validation_prefix_selection_checks_contract_and_lengths(self):
        with tempfile.TemporaryDirectory() as directory:
            for index in range(2):
                np.savez(Path(directory) / f"{index:06d}-0000.npz",
                         input_ids=np.array([1, 101, 102, 103, 104]), contract_sha256="test")
            fixtures = validation_prefixes(directory, "test", lengths=(2, 4))
            self.assertEqual([len(ids) for _, ids in fixtures], [2, 2, 4, 4])
            self.assertTrue(all("input_ids" not in metadata for metadata, _ in fixtures))
            with self.assertRaises(ValueError):
                validation_prefixes(directory, "wrong", lengths=(2,))
            with self.assertRaises(ValueError):
                validation_prefixes(directory, "test", lengths=(6,))

    def test_prefix_replay_branch_reset_and_virtual_slot_match_rollout(self):
        config = CountConfig(max_context=2)
        background = CountTable(config)
        background.freeze()
        rule = BoundaryRule((-3, 0.1, 0, 1, 0.1), 4, 0.375)
        adapter = CountPatcherAdapter(config, rule, background)
        prefixes = [[1, 101], [1, 101, 102], [1, 101, 102], [1, 101, 102, 101, 2],
                    [1, 101, 103], [1, 104], [1, 101, 101, 101, 101]]
        with torch.inference_mode():
            for prefix in prefixes:
                expected = decision_patch_lengths(rollout(prefix, config=config, rule=rule, background=background))
                lengths = adapter.patch_lengths(torch.tensor([prefix]))
                self.assertEqual(lengths.tolist(), [expected])
                self.assertEqual(lengths.sum().item(), len(prefix) + 1)
                self.assertEqual(lengths.dtype, torch.long)
            adapter.reset()
            self.assertEqual(adapter._patcher.model.position, 0)
            adapter.patch_lengths(torch.tensor([prefixes[0]]))
            self.assertEqual(adapter._patcher.model.position, 2)

    def test_inference_guards_and_patch_length_cap(self):
        config = CountConfig(max_context=2)
        background = CountTable(config)
        background.freeze()
        adapter = CountPatcherAdapter(config, BoundaryRule((-100, 0, 0, 0, 0), 4), background)
        with self.assertRaises(ValueError):
            adapter.patch_lengths(torch.tensor([[1, 100]]))
        with torch.inference_mode():
            for invalid in (torch.tensor([[1]]), torch.tensor([[1, 3]]), torch.tensor([[1, 260]]),
                            torch.tensor([[1, 100], [1, 100]]), torch.tensor([[1., 100.]])):
                with self.assertRaises(ValueError):
                    adapter.patch_lengths(invalid)
            lengths = adapter.patch_lengths(torch.tensor([[1, 100, 101, 102, 103, 104]]), max_patch_length=2)
            self.assertEqual(lengths.tolist(), [[1, 2, 2, 2]])
            for cap in (0, -1, True):
                with self.assertRaises(ValueError):
                    adapter.patch_lengths(torch.tensor([[1, 100]]), max_patch_length=cap)


if __name__ == "__main__":
    unittest.main()