"""Explicitly built C++ kernel matching datasketch's uint64 permutation arithmetic."""

import ctypes
from pathlib import Path
import subprocess
import sys


def build_native(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    library = directory / ("minhash.dylib" if sys.platform == "darwin" else "minhash.so")
    if library.exists():
        raise FileExistsError(library)
    source = Path(__file__).parent / "native" / "minhash.cpp"
    flags = ["-nostdlib++"] if sys.platform == "darwin" else []
    subprocess.run(["c++", "-std=c++17", "-O3", "-shared", "-fPIC", *flags, str(source), "-o", str(library)], check=True)
    return library


class NativeMinHash:
    def __init__(self, library):
        self.library = ctypes.CDLL(str(library))
        self.kernel = self.library.blt_minhash128
        self.kernel.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t,
                                ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64),
                                ctypes.POINTER(ctypes.c_uint64), ctypes.c_int]
        self.kernel.restype = None

    def values(self, hashes, multipliers, offsets, scheme="legacy"):
        if scheme not in ("legacy", "affine32"):
            raise ValueError(f"Unsupported MinHash scheme: {scheme}")
        if len(multipliers) != 128 or len(offsets) != 128:
            raise ValueError("Exactly 128 permutations required")
        inputs = (ctypes.c_uint32 * len(hashes))(*hashes)
        factors = (ctypes.c_uint64 * 128)(*multipliers)
        shifts = (ctypes.c_uint64 * 128)(*offsets)
        output = (ctypes.c_uint64 * 128)()
        self.kernel(inputs, len(hashes), factors, shifts, output, int(scheme == "affine32"))
        return list(output)

    def signatures(self, texts, multipliers, offsets, scheme="legacy", threads=1):
        """Return uint32 signatures for already-normalized UTF-8 texts."""
        import numpy as np

        if scheme not in ("legacy", "affine32"):
            raise ValueError(f"Unsupported MinHash scheme: {scheme}")
        if type(threads) is not int or threads < 1:
            raise ValueError("threads must be a positive integer")
        batch = self.library.blt_minhash128_batch
        batch.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint64), ctypes.c_uint64,
                          ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.c_int,
                          ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)]
        batch.restype = ctypes.c_int
        boundaries = np.zeros(len(texts) + 1, dtype=np.uint64)
        np.cumsum([len(text) for text in texts], out=boundaries[1:])
        factors = np.ascontiguousarray(multipliers, dtype=np.uint64)
        shifts = np.ascontiguousarray(offsets, dtype=np.uint64)
        output = np.empty((len(texts), 128), dtype=np.uint32)
        status = batch(b"".join(texts), boundaries.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)), len(texts),
                       factors.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)),
                       shifts.ctypes.data_as(ctypes.POINTER(ctypes.c_uint64)), int(scheme == "affine32"), threads,
                       output.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)))
        if status != 0:
            raise RuntimeError(f"Native MinHash batch failed: {status}")
        return output