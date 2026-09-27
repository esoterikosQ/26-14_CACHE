"""Incremental BLT cache; explicit opt-in for inference only."""

from .frontier import patch_starts, shared_closed_patch_count

__all__ = ["GlobalPrefixReuse", "patch_starts", "shared_closed_patch_count"]


def __getattr__(name):
    if name == "GlobalPrefixReuse":
        from .global_reuse import GlobalPrefixReuse
        return GlobalPrefixReuse
    raise AttributeError(name)
