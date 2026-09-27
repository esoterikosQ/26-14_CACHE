# Future `phdq3` integration

The currently queued native training job uses the in-tree `blt_hf.cache`
implementation. Do not change its checkout, run identity, or imported cache
code while that job is pending/running. The extraction becomes a dependency
for **new** runs only after the standalone repository is published and tested.

1. Publish this directory as an independent GitHub repository. Record its
   full commit SHA, not a moving branch name.
2. In the prepared Mac/itcerdo/Neuron environment, install the pinned source:

   ```bash
   python -m pip install --no-deps \
     "phdq-blt-cache @ git+https://github.com/esoterikosQ/blt-cache.git@<COMMIT_SHA>"
   python -c 'from phdq_blt_cache import GlobalPrefixReuse; print(GlobalPrefixReuse)'
   ```

   Replace the URL if the actual repository name differs. `--no-deps` keeps
   the already prepared CUDA/BF16 PyTorch environment intact; check version
   compatibility separately. This is a VCS dependency installation, not a
   remote Python import.
3. Replace `from .cache.global_reuse import GlobalPrefixReuse` in
   `blt_hf/generation.py` with the installed package import for a **new**
   backend. Preserve the existing backend and its past run evidence until
   parity of the installed package is established.
4. Add the exact external package commit and installed source digest to the
   `phdq3` run/evaluation identity. Its current `code_identity` only hashes
   local `blt_hf/cache/*`; changing the import without changing this identity
   would allow different cache implementations to share one run signature.
   Update train, eval, and benchmark identity/manifest paths consistently.
5. Re-run local integration tests and same-GPU HF-versus-installed-cache
   generation. The user then runs the Neuron full-split comparison. A new
   run gets a fresh `RUN_ID`/`EVAL_DIR`; never resume an old run with new
   package code.

The owning repository's `blt_hf/generation.py`, `blt_hf/train.py`,
`blt_hf/eval.py`, `blt_hf/runtime.py`, and `blt_hf_checks/compare_cache_eval.py`
are integration touchpoints, not files to copy into this package.
