---
name: blt-cache-development
description: Develop and validate the standalone PHDQ BLT inference cache, including patch invalidation, guarded reuse, and integration with the BLT training project.
---

# BLT cache development

Read `docs/HANDOFF.md` for the current package boundary and host permissions.
Read `docs/PLAN.md` for the next experiment; consult `docs/DESIGN_HISTORY.md`
when changing patch frontier or state reuse.

Keep cache code importable without the `phdq3` source tree. Use explicit
backend names and preserve the previous behavior for comparison. The model
object is a runtime input; model weights and research datasets stay outside
this repository.

For each change to reused state, compare complete token IDs, EOS, UTF-8, and
text against uncached generation on the same model, input, GPU, and generation
settings. Record code and model identities, guard refreshes, generation-only
time, and memory. A few matching prefixes do not establish full-split parity.
The existing guarded native A100 parity is limited to beam 1 and batch 1.

Run local package tests first. Itcerdo is the user's personally managed
server; the 2026-10-19 clarification removes the former inference-only and
project-path limits. Training is permitted within requested tasks; preserve
existing jobs, environments, and data. Prepare Neuron commands and analyze
returned logs; the user handles Neuron access and
submissions. Integrate into `phdq3` only after the running training job ends,
pin the package Git commit, and add that external code identity to run/eval
manifests before a new run uses it.
