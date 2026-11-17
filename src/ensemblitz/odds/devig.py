"""Remove the bookmaker margin from prices. Pure functions on NumPy arrays."""

from __future__ import annotations

import numpy as np


def implied(decimal_odds: np.ndarray) -> np.ndarray:
    return 1.0 / np.asarray(decimal_odds, dtype=float)


def multiplicative(decimal_odds: np.ndarray) -> np.ndarray:
    """Fair probabilities by proportional scaling of the implied probabilities."""
    q = implied(decimal_odds)
    return q / q.sum()


def shin(decimal_odds: np.ndarray, tol: float = 1e-10) -> np.ndarray:
    """Shin (1993): assumes a share ``z`` of insider money; it takes more margin from longshots.

    Solves for z with bisection so the fair probabilities sum to one. With two outcomes and a
    small margin it is close to the multiplicative method, but it removes less from favourites.
    """
    q = implied(decimal_odds)
    s = q.sum()
    if s <= 1.0:
        return q / s

    def probs(z: float) -> np.ndarray:
        return (np.sqrt(z * z + 4 * (1 - z) * q * q / s) - z) / (2 * (1 - z))

    lo, hi = 0.0, 0.4
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if probs(mid).sum() > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    p = probs(0.5 * (lo + hi))
    return p / p.sum()


def overround(decimal_odds: np.ndarray) -> float:
    return float(implied(decimal_odds).sum() - 1.0)
