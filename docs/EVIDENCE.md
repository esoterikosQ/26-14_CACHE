# Experiment evidence index

The `evidence/` directory is a copy of the small `p3a_*.json` reports from
`phdq3/blt_hf_checks/results/` at export time. It is historical evidence, not
an executable fixture or a replacement for raw model/data identities.

| Question | Main report | Finding |
| --- | --- | --- |
| Can earlier patch boundaries move? | `p3a_patch_causality_20260926_v2.json` | Yes, observed BF16 threshold crossings in mixed prefixes. |
| Are closed activations numerically stable? | `p3a_state_stability_repeat_20260926.json` | No across input lengths; same-length repeat was stable in the tested set. |
| Does simple global reuse preserve full native output? | `p3a_native_full_global_06.json` | No, 32/2,634 strings differed. |
| What caused first divergences? | `p3a_native_divergence_diag_07.json`, `p3a_native_divergence_logit_shape_08.json` | Both global skip and the HF `logits_to_keep=1` shape mattered. |
| Does guarded reuse preserve native output and save time? | `p3a_native_full_guarded_11.json` | Yes for that A100/native/beam-1/batch-1 run: 2,634/2,634 matched; generation-only 1.314x faster. |

Each report is tied to its original `phdq3` code/model/evaluation identity.
Do not substitute these results for tests of the independently installed
package or a future modified cache.
