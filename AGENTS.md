# Work on the standalone BLT cache

Read `docs/HANDOFF.md` and `docs/PLAN.md` before implementation. For cache
invalidation or decoder work, also read `docs/DESIGN_HISTORY.md`.

Keep this repository an installable Python package independent of the
`phdq3` source tree. Do not copy pretrained weights, provided datasets,
tokenizers, optimizer checkpoints, or Slurm outputs here. Preserve the public
`phdq_blt_cache` import and require explicit opt-in for new cache behavior.

## Reference-only projects

As clarified by the user on 2026-10-29, `phdq3` is read-only reference for
this work. Write all new code, configurations, commands, tests and progress
logs in `blt-cache`, never in `phdq3`. Maintain the entropy runtime directly
under `neuron/runtime/`; do not edit the reference project and export it.
Neuron data and output paths belong under `/scratch/r984a02/blt-cache`.
The user executes all Neuron operations and transfers reviewed runtime logs
through GitHub using `runtimelog/`. Small sanitized logs are allowed there;
never commit secrets, raw corpora, weights or optimizer checkpoints.

The native A100 validation comparison supports output parity for one guarded
beam-1/batch-1 configuration only. Do not generalize it to other datasets,
models, beams, GPU architectures, or decoder caching without new measurements.
The user performs Neuron access, transfer, and job submission. Itcerdo is the
user's personally managed server. As clarified on 2026-10-19, it has no
inference-only, training, or project-path restrictions. Keep work within the
requested task and preserve existing jobs, environments, and data.

The reusable project workflow is in `skills/blt-cache-development/SKILL.md`.
New Codex project tasks may load that file explicitly; installing it into a
personal skills directory is optional.

## Required progress log

Read the latest entries in root `log.md` before continuing project work.
Append a dated entry at each meaningful stage transition, completed check,
experiment result, failure, or blocker, before moving to the next stage.
Do not wait until the whole task ends or report results only in chat.
Record the stage, work performed, settings/commands or artifact links,
observed results and validation, limitations, and next action. Distinguish
measured results from hypotheses and proposed work. Preserve chronological
history; append corrections rather than silently rewriting prior outcomes.
Mark retrospective entries explicitly and never invent execution timestamps.
Keep secrets, raw datasets, weights, and large command outputs out of the log.
Update `task.md` status alongside the log when applicable, and ensure the log
is current before the final response.
