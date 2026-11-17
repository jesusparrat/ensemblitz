"""Small stateful rating helpers. Every rating is read *before* a game and updated *after* it."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


class DecayedMean:
    """Exponentially decayed weighted mean shrunk towards ``prior_mean``.

    value = (sum_wx + prior_w * prior_mean) / (sum_w + prior_w), where both sums decay by
    ``decay`` at every update of that key. ``new_season`` shrinks the evidence, which is the
    "preseason regression to the mean": less history means the prior weighs more.
    """

    def __init__(self, decay: float, prior_w: float, prior_mean: float = 0.0) -> None:
        self.decay, self.prior_w, self.prior_mean = decay, prior_w, prior_mean
        self.sw: dict[str, float] = defaultdict(float)
        self.swx: dict[str, float] = defaultdict(float)

    def value(self, key: str) -> float:
        return (self.swx[key] + self.prior_w * self.prior_mean) / (self.sw[key] + self.prior_w)

    def weight(self, key: str) -> float:
        return self.sw[key]

    def update(self, key: str, x: float, w: float) -> None:
        if w <= 0:
            return
        self.sw[key] = self.sw[key] * self.decay + w
        self.swx[key] = self.swx[key] * self.decay + w * x

    def new_season(self, keep: float) -> None:
        for k in list(self.sw):
            self.sw[k] *= keep
            self.swx[k] *= keep


@dataclass(frozen=True)
class EloParams:
    k: float = 20.0
    hfa: float = 48.0
    base: float = 1500.0
    season_regress: float = 1 / 3


class Elo:
    """Elo with margin-of-victory multiplier (FiveThirtyEight style)."""

    def __init__(self, params: EloParams | None = None) -> None:
        self.p = params or EloParams()
        self.r: dict[str, float] = defaultdict(lambda: self.p.base)

    def diff(self, home: str, away: str, neutral: bool) -> float:
        """Home rating minus away rating, including home-field advantage."""
        return self.r[home] - self.r[away] + (0.0 if neutral else self.p.hfa)

    def update(self, home: str, away: str, margin: float, neutral: bool) -> None:
        d = self.diff(home, away, neutral)
        exp_home = 1.0 / (1.0 + 10 ** (-d / 400.0))
        actual = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        winner_diff = d if margin >= 0 else -d
        mult = _log1p_abs(margin) * 2.2 / (winner_diff * 0.001 + 2.2)
        delta = self.p.k * mult * (actual - exp_home)
        self.r[home] += delta
        self.r[away] -= delta

    def new_season(self) -> None:
        for t in list(self.r):
            self.r[t] += (self.p.base - self.r[t]) * self.p.season_regress


def _log1p_abs(x: float) -> float:
    import math

    return math.log(abs(x) + 1.0)
