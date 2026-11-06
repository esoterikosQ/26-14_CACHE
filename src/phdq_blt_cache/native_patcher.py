"""Explicit loading of a separately built CPython count-patcher extension."""

from functools import lru_cache
import importlib.util
from pathlib import Path


@lru_cache(maxsize=8)
def load_count_native(library):
    library = Path(library).resolve(strict=True)
    spec = importlib.util.spec_from_file_location("_count_patcher_probe", library)
    if spec is None or spec.loader is None:
        raise ImportError(f"Not a loadable count-patcher extension: {library}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "create", None)) or not callable(getattr(module, "run", None)):
        raise ImportError("Count-patcher extension must provide create and run")
    return module