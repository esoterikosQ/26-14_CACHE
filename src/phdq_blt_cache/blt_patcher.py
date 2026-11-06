"""Opt-in patch-length inputs for unpadded, batch-one BLT inference."""

from dataclasses import asdict

from .count_patcher import SequentialPatcher, decision_patch_lengths


class CountPatcherAdapter:
    """Keep causal count state while BLT receives complete-prefix tensors."""

    def __init__(self, config, rule, background, *, backend="python", native_library=None):
        if backend not in ("python", "cpp"):
            raise ValueError("Expected python or cpp count backend")
        if backend == "python" and native_library is not None:
            raise ValueError("native_library requires explicit backend='cpp'")
        self.backend = backend
        if backend == "cpp":
            if native_library is None:
                raise ValueError("C++ backend requires an explicitly built native_library")
            if config.window is not None or (config.vocab_size, config.eos_id, config.pad_id) != (260, 2, 3):
                raise ValueError("C++ backend requires unlimited-window BLT byte counts")
            if not background._frozen or background.config.max_context < config.max_context or any(
                getattr(background.config, name) != getattr(config, name)
                for name in ("vocab_size", "eos_id", "pad_id")
            ):
                raise ValueError("C++ backend requires frozen compatible background counts")
            from .native_patcher import load_count_native

            self._native_module = load_count_native(native_library)
        self.config = config
        self.rule = rule
        self.background = background
        self.reset()

    def reset(self):
        self._ids = []
        self._decisions = []
        if self.backend == "cpp":
            self._native_state = self._native_module.create(asdict(self.config), asdict(self.rule), self.background.lookup)
        else:
            self._patcher = SequentialPatcher(self.config, self.rule, self.background)

    def patch_lengths(self, input_ids, *, max_patch_length=None):
        import torch

        if torch.is_grad_enabled():
            raise ValueError("Count patching requires inference_mode or no_grad")
        if input_ids.ndim != 2 or input_ids.shape[0] != 1 or input_ids.shape[1] < 2:
            raise ValueError("Expected an unpadded batch-one prefix with at least two IDs")
        if input_ids.dtype != torch.long:
            raise ValueError("Expected torch.long byte IDs")
        if max_patch_length is not None and (type(max_patch_length) is not int or max_patch_length < 1):
            raise ValueError("max_patch_length must be a positive integer or None")
        token_ids = input_ids[0].tolist()
        if any(type(token_id) is not int or not 0 <= token_id < self.config.vocab_size
               or token_id == self.config.pad_id for token_id in token_ids):
            raise ValueError("Invalid or padded byte IDs")
        if len(token_ids) < len(self._ids) or token_ids[:len(self._ids)] != self._ids:
            self.reset()
        if self.backend == "cpp":
            lengths = self._native_module.run(self._native_state, token_ids)
        else:
            self._decisions.extend(self._patcher.append(token_ids[len(self._ids):], start_position=len(self._ids)))
            lengths = decision_patch_lengths(self._decisions + [self._patcher.predict_boundary()])
        self._ids = token_ids
        if max_patch_length is not None:
            bounded = []
            for length in lengths:
                full, remainder = divmod(length, max_patch_length)
                bounded.extend([max_patch_length] * full)
                if remainder:
                    bounded.append(remainder)
            lengths = bounded
        return torch.tensor([lengths], dtype=torch.long, device=input_ids.device)