# Standalone cache project handoff

This export was prepared from `phdq3` `main` commit `6dbdb4f` on 2026-09-27.
The new repository owns `src/phdq_blt_cache/`, tests, this plan, and future
cache inference improvements. `phdq3` continues to own model conversion,
training, generation orchestration, GLEU/M2 scoring, data, checkpoints, and
Neuron submission scripts. The two projects should communicate through a
pinned Python package API rather than a copied `blt_hf/cache` directory.

## Source and current status

- `src/phdq_blt_cache/frontier.py` and `global_reuse.py` were copied from
  `phdq3/blt_hf/cache/` at the commit above. The guarded backend in `phdq3`
  currently calls `GlobalPrefixReuse.run(..., logits_to_keep=1,
  guard_margin=1.0)` with decoder reuse disabled.
- Full native A100 validation comparison: 2,634/2,634 generated token IDs,
  EOS, and strings matched the HF baseline. Generation-only time was
  9,074.30 s HF versus 6,906.76 s guarded (1.314x). The report is
  `evidence/p3a_native_full_guarded_11.json`. This does not prove parity for
  another model, dataset, beam count, batch size, device, or code change.
- The guard margin 1.0 is an experimental heuristic. It was set after
  observed BF16 first-divergence gaps, not from an external error guarantee.
  Preserve output comparisons whenever it or the reuse rule changes.
- The copied `docs/ORIGINAL_P3A_PLAN.md` and `docs/DESIGN_HISTORY.md` preserve
  prior reasoning. Some lines predate experiment 11; use `docs/PLAN.md` for
  current next steps.

## Runtime contract

`GlobalPrefixReuse` requires a model whose `.model` has `patcher`,
`global_transformer`, and `local_decoder` modules with the `phdq3` OSC BLT
forward signatures. Inputs must be unpadded batch 1 byte-token prefixes,
extended by one byte each call, with `model.eval()` and
`torch.inference_mode()`. The guarded path requires `logits_to_keep=1` and
`reuse_decoder=False`. The class returns model output plus reuse diagnostics;
it does not perform byte selection or decode text. It temporarily replaces
module `forward` methods during a call, so do not share one model instance
between concurrent cache calls.

The package is not yet a remote GitHub repository. The README install URL is
a template. Use `docs/PUBLISH_GITHUB.md` to create the remote repository,
push this project, pin its commit, and validate installation before changing
the running BLT project. Do not claim `pip` can import code directly from
GitHub without installing it.

## Host and data boundaries

- Mac: edit code, run pure Python checks, review JSON evidence.
- Itcerdo: the user's prior authorization is for BF16 inference and profiling
  inside `/home/itcmaster/projects/phdq3`; no optimizer, backward, or
  fine-tuning. A separate Git repository checkout can be placed under that
  allowed tree without turning it into a `phdq3` Git worktree. Model files
  remain read-only inputs, not Git content.
- Neuron: only the user connects, transfers, and submits Slurm jobs. Prepare
  commands and analyze returned logs here. Do not ask the user to interrupt
  the currently queued native training job for this extraction.
- Research data and third-party validation/test splits are not copied into
  this package. Package tests use synthetic inputs; integration checks use
  data from the owning BLT project without editing it.

The reusable Codex workflow lives in
`skills/blt-cache-development/SKILL.md`. The new project's `AGENTS.md`
points to it. For automatic personal skill discovery, copy that skill folder
to `$CODEX_HOME/skills/` in the new Codex environment; project work itself
does not depend on installing the skill.
