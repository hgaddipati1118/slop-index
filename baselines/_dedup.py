"""Shared exact + near-duplicate detection for baseline filters.

Factored out of the original email/filter.py MinHash-LSH implementation so
the three newer domain filters (slack, essay, social) don't each carry their
own copy of the same ~80 lines of hashing math. Behavior is identical to
what email/filter.py inlines: normalized-text exact hash + 5-gram-shingle
MinHash-LSH banding, Jaccard >= threshold. email/filter.py itself is left
untouched (it's the frozen template); this module exists only for the three
new domains built after it.

Usage:
    from _dedup import normalized_hash, shingles, NearDupIndex

    seen_hashes = set()
    ndi = NearDupIndex(seed=SEED)
    h = normalized_hash(text)
    if h in seen_hashes: ... # exact dup
    sh = shingles(toks)
    if ndi.is_duplicate(sh): ... # near dup
    else: ndi.add(sh)
"""
import hashlib
import random
import re


def normalized_hash(text: str) -> str:
    norm = re.sub(r"[^a-z0-9 ]", "", text.lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    return hashlib.sha1(norm.encode()).hexdigest()


def shingles(toks, k=5):
    lower = [t.lower() for t in toks]
    if len(lower) < k:
        return {" ".join(lower)}
    return {" ".join(lower[i : i + k]) for i in range(len(lower) - k + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class NearDupIndex:
    """Banded MinHash-LSH near-duplicate index (same params as email/filter.py:
    8 hash functions, 2 bands of 4 rows, Jaccard >= threshold)."""

    def __init__(self, seed: int, num_hashes: int = 8, num_bands: int = 2, threshold: float = 0.8):
        assert num_hashes % num_bands == 0
        self.num_hashes = num_hashes
        self.num_bands = num_bands
        self.rows_per_band = num_hashes // num_bands
        self.threshold = threshold
        self._mersenne = (1 << 61) - 1
        rnd = random.Random(seed)
        self._coeffs = [(rnd.randrange(1, self._mersenne), rnd.randrange(0, self._mersenne))
                         for _ in range(num_hashes)]
        self.bands = [dict() for _ in range(num_bands)]
        self.shingle_sets = {}
        self._next_idx = 0

    def _sig(self, sh: set):
        hashed = [int(hashlib.md5(s.encode()).hexdigest(), 16) for s in sh]
        return tuple(min((a * h + b) % self._mersenne for h in hashed) for a, b in self._coeffs)

    def is_duplicate(self, sh: set) -> bool:
        sig = self._sig(sh)
        candidates = set()
        for bi in range(self.num_bands):
            key = sig[bi * self.rows_per_band : (bi + 1) * self.rows_per_band]
            candidates |= set(self.bands[bi].get(key, []))
        for cidx in candidates:
            if jaccard(sh, self.shingle_sets[cidx]) >= self.threshold:
                return True
        return False

    def add(self, sh: set):
        sig = self._sig(sh)
        idx = self._next_idx
        self._next_idx += 1
        self.shingle_sets[idx] = sh
        for bi in range(self.num_bands):
            key = sig[bi * self.rows_per_band : (bi + 1) * self.rows_per_band]
            self.bands[bi].setdefault(key, []).append(idx)
        return idx
