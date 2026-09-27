# Cache development plan after project split

## Current baseline

The guarded beam-1/batch-1 global cache is the reference implementation.
It rechecks entropy patching and the local encoder for every byte, skips the
global forward only when the patch starts are unchanged, and refreshes full
forward for close top-two legal byte logits. Decoder KV reuse remains off.
The native A100 validation output parity and measured speed are documented
in `HANDOFF.md` and `evidence/p3a_native_full_guarded_11.json`.

## Next work in this repository

1. Make the copied package reproducible: install it in the prepared BF16
   environment, run package tests, and run a short actual 1B OSC model smoke
   using the import `from phdq_blt_cache import GlobalPrefixReuse`. Verify
   that the installed copy exactly reproduces the current local implementation
   before changing cache behavior.
2. Profile guarded generation on itcerdo using the same model, prompts, dtype,
   and GPU for baseline and candidate. Report first-call and steady-state
   costs separately for entropy/patcher, local encoder, global transformer,
   and local decoder; record patch changes and guard refreshes. Do not use
   5090 timings to claim A100 improvement.
3. Improve one reuse component at a time. For local encoder reuse or more
   aggressive global reuse, specify the exact patch-frontier invalidation,
   positions, masks, BF16 shape effects, and fallback rule. Preserve the
   baseline guarded backend and give each new candidate a distinct name.
   Decoder KV caching is an optional separate experiment; prior measurements
   did not show a speed benefit. Do not assume it is required for the next
   speedup.
4. Compare every generated token ID, EOS, UTF-8 validity, and final string
   against uncached generation on identical inputs. Start with adversarial
   prefixes and short complete sentences, then ask the user to run full native
   validation on Neuron A100 if the candidate passes. Record mismatches,
   generation-only time, p50/p95, and peak memory. Other datasets and beam 4
   need their own verification.
5. Once the user-provided Neuron evidence supports adoption, hand the
   candidate's Git commit and API contract to `phdq3`. Update only a new BLT
   run after the currently queued native job is finished. Pin the package
   commit and include that external source identity in train/eval manifests.

## Acceptance for a candidate

Correctness is first: the candidate must match the corresponding HF no-cache
generation output for the claimed model, split, beam, batch, and device
conditions. Measure a real generation-time improvement without counting
load/setup as generation. Report all conditions and residual limits. Do not
use a previous run's output directory or checkpoint identity for changed
cache code. Performance targets are goals, not a reason to discard a correct
candidate without reviewing its tradeoffs with the user.
