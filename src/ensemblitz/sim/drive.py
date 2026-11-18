"""Vectorised drive-level game simulator.

Pure functions, NumPy arrays in / NumPy arrays out, no pandas, no I/O, no globals except the
frozen ``SimParams``. This is on purpose: the same signature can be implemented in Rust (PyO3 +
``numpy`` crate) and swapped in without touching callers.

Model (v0.1): each team has ``n`` possessions. A possession ends in a touchdown, a field goal or
nothing (punt, turnover, downs, end of half). Per-possession probabilities are derived from the
team's *expected points per possession*, which in turn comes from the team ratings
(``exp_points`` per team per game). A touchdown is worth 6 plus an extra point (94%), a two-point
conversion (3%) or nothing (3%). Overtime is a short alternating-possession sudden-death routine.
Not modelled yet: safeties, defensive/special-teams scores, clock, in-game injuries, weather.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TD_BASE_POINTS = 6.0


@dataclass(frozen=True)
class SimParams:
    league_td: float = 0.215  # P(touchdown) per possession for an average offence
    league_fg: float = 0.125  # P(field goal) per possession
    td_exponent: float = 1.0  # how fast TD rate scales with team quality
    fg_exponent: float = 0.4  # FG rate scales slower than TD rate
    xp_prob: float = 0.94
    two_pt_prob: float = 0.03  # P(two-point conversion succeeds) per touchdown
    drives_mean: float = 23.0  # possessions per game, both teams
    drives_sd: float = 2.2
    drives_min: int = 17
    drives_max: int = 31
    ot_drives: int = 8

    @property
    def td_points(self) -> float:
        return TD_BASE_POINTS + self.xp_prob + 2.0 * self.two_pt_prob

    @property
    def league_points_per_drive(self) -> float:
        return self.league_td * self.td_points + self.league_fg * 3.0


def drive_probabilities(
    exp_points: np.ndarray, drives: np.ndarray | float, p: SimParams
) -> tuple[np.ndarray, np.ndarray]:
    """Map expected points per game to per-possession (P_td, P_fg).

    Solves for a quality scale ``s`` so that ``P_td*td_points + P_fg*3`` matches the expected
    points per possession exactly (bisection, vectorised).
    """
    target = np.asarray(exp_points, float) / np.asarray(drives, float)

    def pts(s: np.ndarray) -> np.ndarray:
        td = np.clip(p.league_td * s**p.td_exponent, 0.0, 0.6)
        fg = np.clip(p.league_fg * s**p.fg_exponent, 0.0, 0.3)
        return td * p.td_points + fg * 3.0

    lo, hi = np.full_like(target, 0.05), np.full_like(target, 4.0)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        up = pts(mid) < target
        lo, hi = np.where(up, mid, lo), np.where(up, hi, mid)
    s = 0.5 * (lo + hi)
    td = np.clip(p.league_td * s**p.td_exponent, 0.0, 0.6)
    fg = np.clip(p.league_fg * s**p.fg_exponent, 0.0, 0.3)
    return td, fg


def _team_points(
    td: np.ndarray,
    fg: np.ndarray,
    n_drives: np.ndarray,
    rng: np.random.Generator,
    p: SimParams,
    max_drives: int,
) -> np.ndarray:
    """Points over ``n_drives`` possessions. td, fg: (G,1); n_drives: (G,N) -> returns (G,N)."""
    g, n = n_drives.shape
    u = rng.random((g, n, max_drives))
    is_td = u < td[..., None]
    is_fg = (u >= td[..., None]) & (u < (td + fg)[..., None])
    valid = np.arange(max_drives)[None, None, :] < n_drives[..., None]
    v = rng.random((g, n, max_drives))
    extra = np.where(v < p.xp_prob, 1.0, np.where(v < p.xp_prob + p.two_pt_prob, 2.0, 0.0))
    pts = np.where(is_td, TD_BASE_POINTS + extra, np.where(is_fg, 3.0, 0.0))
    return (pts * valid).sum(axis=2)


def simulate_games(
    exp_points_home: np.ndarray,
    exp_points_away: np.ndarray,
    n_sims: int = 5000,
    seed: int = 0,
    params: SimParams | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate final scores.

    Args:
        exp_points_home, exp_points_away: shape (G,), expected regulation points of each team.
        n_sims: simulations per game.
    Returns:
        (home_scores, away_scores), each int array of shape (G, n_sims).
    """
    p = params or SimParams()
    rng = np.random.default_rng(seed)
    eh = np.asarray(exp_points_home, float).reshape(-1)
    ea = np.asarray(exp_points_away, float).reshape(-1)
    g = eh.shape[0]
    total = np.clip(
        np.rint(rng.normal(p.drives_mean, p.drives_sd, (g, n_sims))), p.drives_min, p.drives_max
    )
    home_extra = rng.random((g, n_sims)) < 0.5  # who gets the odd possession
    d_home = np.where(home_extra, np.ceil(total / 2), np.floor(total / 2))
    d_away = total - d_home
    td_h, fg_h = drive_probabilities(eh, p.drives_mean / 2, p)
    td_a, fg_a = drive_probabilities(ea, p.drives_mean / 2, p)
    hs = _team_points(td_h[:, None], fg_h[:, None], d_home, rng, p, p.drives_max // 2 + 1)
    as_ = _team_points(td_a[:, None], fg_a[:, None], d_away, rng, p, p.drives_max // 2 + 1)

    tied = hs == as_
    if tied.any():
        hs, as_ = _overtime(hs, as_, tied, td_h, fg_h, td_a, fg_a, rng, p)
    return hs.astype(np.int64), as_.astype(np.int64)


def _overtime(hs, as_, tied, td_h, fg_h, td_a, fg_a, rng, p: SimParams):
    """Alternating possessions: a first-drive TD wins; otherwise both teams get a drive, then
    sudden death. A coin flip decides who receives."""
    hs, as_ = hs.copy(), as_.copy()
    g, n = hs.shape
    home_first = rng.random((g, n)) < 0.5
    ot_h = np.zeros((g, n))
    ot_a = np.zeros((g, n))
    done = ~tied
    for k in range(p.ot_drives):
        home_turn = home_first if k % 2 == 0 else ~home_first
        td = np.where(home_turn, td_h[:, None], td_a[:, None])
        fg = np.where(home_turn, fg_h[:, None], fg_a[:, None])
        u = rng.random((g, n))
        pts = np.where(u < td, 7.0, np.where(u < td + fg, 3.0, 0.0))
        live = ~done
        ot_h += np.where(live & home_turn, pts, 0.0)
        ot_a += np.where(live & ~home_turn, pts, 0.0)
        first_td_win = (k == 0) & (pts >= 6)
        both_had_ball = k >= 1
        decided = live & (first_td_win | (both_had_ball & (ot_h != ot_a)))
        done = done | decided
    hs = np.where(tied, hs + ot_h, hs)
    as_ = np.where(tied, as_ + ot_a, as_)
    return hs, as_


def summarize_sim(home: np.ndarray, away: np.ndarray) -> dict[str, np.ndarray]:
    """Reduce simulated scores (G, N) to per-game summaries (arrays of shape (G,))."""
    margin = home - away
    total = home + away
    g, n = home.shape
    mode_h = np.zeros(g, int)
    mode_a = np.zeros(g, int)
    mode_p = np.zeros(g)
    for i in range(g):
        key = home[i] * 200 + away[i]
        vals, counts = np.unique(key, return_counts=True)
        j = counts.argmax()
        mode_h[i], mode_a[i], mode_p[i] = vals[j] // 200, vals[j] % 200, counts[j] / n
    return {
        "p_home": (margin > 0).mean(axis=1) + 0.5 * (margin == 0).mean(axis=1),
        "p_tie": (margin == 0).mean(axis=1),
        "margin_mean": margin.mean(axis=1),
        "margin_sd": margin.std(axis=1),
        "margin_q10": np.quantile(margin, 0.1, axis=1),
        "margin_q90": np.quantile(margin, 0.9, axis=1),
        "total_mean": total.mean(axis=1),
        "total_sd": total.std(axis=1),
        "total_q10": np.quantile(total, 0.1, axis=1),
        "total_q90": np.quantile(total, 0.9, axis=1),
        "home_mean": home.mean(axis=1),
        "away_mean": away.mean(axis=1),
        "home_q10": np.quantile(home, 0.1, axis=1),
        "home_q90": np.quantile(home, 0.9, axis=1),
        "away_q10": np.quantile(away, 0.1, axis=1),
        "away_q90": np.quantile(away, 0.9, axis=1),
        "mode_home": mode_h,
        "mode_away": mode_a,
        "mode_prob": mode_p,
    }


def likely_score(
    home: np.ndarray,
    away: np.ndarray,
    pick_home: np.ndarray,
    margin: np.ndarray,
    width: float = 3.5,
) -> dict[str, np.ndarray]:
    """A representative final score that agrees with the predicted winner and margin.

    The raw mode of the joint score distribution is dominated by football's scoring lattice
    (7s and 3s), so many games share 24-17. Instead: take the simulations where the picked team
    wins by within ``width`` points of the predicted margin, compute their mean score (the centre
    of that region), and return the nearest *reachable and frequent* score (seen in at least 40%
    as many simulations as the most common score in the region). Games with different expected
    totals therefore get different scores. ``prob`` is the raw simulated probability of that
    exact score, so it stays honest (about 1%). Falls back to all simulations if the region is
    empty.
    """
    g, n = home.shape
    size = int(max(home.max(), away.max())) + 1
    hh, aa = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    out_h, out_a, out_p = np.zeros(g, int), np.zeros(g, int), np.zeros(g)
    for i in range(g):
        d = home[i] - away[i]
        sign = 1.0 if pick_home[i] else -1.0
        sel = (sign * d > 0) & (np.abs(d - margin[i]) <= width)
        if not sel.any():
            sel = np.ones(n, bool)
        counts = np.zeros((size, size))
        np.add.at(counts, (home[i][sel], away[i][sel]), 1.0)
        cen_h, cen_a = home[i][sel].mean(), away[i][sel].mean()
        ok = counts >= 0.4 * counts.max()
        dist = np.where(ok, (hh - cen_h) ** 2 + (aa - cen_a) ** 2, np.inf)
        r, c = divmod(int(dist.argmin()), size)
        full = np.zeros((size, size))
        np.add.at(full, (home[i], away[i]), 1.0)
        out_h[i], out_a[i], out_p[i] = r, c, full[r, c] / n
    return {"like_home": out_h, "like_away": out_a, "like_prob": out_p}
