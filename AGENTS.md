# Work on the standalone BLT cache

Read `docs/HANDOFF.md` and `docs/PLAN.md` before implementation. For cache
invalidation or decoder work, also read `docs/DESIGN_HISTORY.md`.

Keep this repository an installable Python package independent of the
`phdq3` source tree. Do not copy pretrained weights, provided datasets,
tokenizers, optimizer checkpoints, or Slurm outputs here. Preserve the public
`phdq_blt_cache` import and require explicit opt-in for new cache behavior.

The native A100 validation comparison supports output parity for one guarded
beam-1/batch-1 configuration only. Do not generalize it to other datasets,
models, beams, GPU architectures, or decoder caching without new measurements.
The user performs Neuron access, transfer, and job submission. Itcerdo work is
limited to BF16 inference/profiling under the previously authorized
`/home/itcmaster/projects/phdq3` tree; no training there.

The reusable project workflow is in `skills/blt-cache-development/SKILL.md`.
New Codex project tasks may load that file explicitly; installing it into a
personal skills directory is optional.
