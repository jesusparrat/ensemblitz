"""Dynamic team strength as a linear-Gaussian state-space model (Kalman filter).

Each team has an offence and a defence strength (points above/below league mean). Points scored:

    pts_home = mu + hfa/2 + off_home + def_away + noise
    pts_away = mu - hfa/2 + off_away + def_home + noise

Strengths follow a random walk week to week and are shrunk towards zero between seasons. This is
the closed-form cousin of a hierarchical Bayesian dynamic model: we get posterior means *and*
covariances in milliseconds, so it can be re-run for every walk-forward step. Hyper-parameters are
tuned by maximum likelihood of the margins on *past seasons only*.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import ndtr

from ensemblitz.data.stadiums import HOME_STADIUMS

TEAMS = sorted(HOME_STADIUMS)
IDX = {t: i for i, t in enumerate(TEAMS)}
N = len(TEAMS)


@dataclass(frozen=True)
class KFParams:
    q: float = 0.03  # weekly random-walk variance of a strength (points^2)
    s0: float = 1.2  # extra variance added at the start of each season
    rho: float = 0.72  # share of strength carried to the next season
    hfa: float = 1.8  # home-field advantage on the margin (points)
    sigma: float = 9.3  # sd of a team's points in a game
    p0: float = 6.0  # prior variance of a strength in the first season

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def run_kf(games: pd.DataFrame, params: KFParams, until_season: int | None = None) -> pd.DataFrame:
    """Pre-game predictions for every game, updating only after each (season, week) batch.

    ``games`` needs: game_id, season, week, home_team, away_team, neutral, home_score, away_score,
    played. Unplayed games get predictions but do not update the state.
    """
    g = games.sort_values(["season", "week", "kickoff_utc", "game_id"])
    if until_season is not None:
        g = g[g["season"] <= until_season]
    x = np.zeros(2 * N)
    P = np.eye(2 * N) * params.p0
    s2 = params.sigma**2
    pts_sum, pts_n = 22.0 * 200, 200.0  # league scoring mean with a weak prior
    out = []
    last_season, last_week = None, None
    for (season, week), batch in g.groupby(["season", "week"], sort=True):
        if last_season is None:
            pass
        elif season != last_season:
            x *= params.rho
            P = params.rho**2 * P + np.eye(2 * N) * params.s0
        else:
            P = P + np.eye(2 * N) * params.q * max(week - last_week, 1)
        last_season, last_week = season, week
        mu = pts_sum / pts_n
        for r in batch.itertuples(index=False):
            h, a = IDX[r.home_team], IDX[r.away_team]
            hfa = 0.0 if r.neutral else params.hfa
            idx = np.array([h, N + a, a, N + h])
            c = np.array([1.0, 1.0, -1.0, -1.0])
            m = hfa + c @ x[idx]
            var = c @ P[np.ix_(idx, idx)] @ c + 2 * s2
            tot_dev = x[idx].sum()
            out.append(
                (
                    r.game_id,
                    m,
                    2 * mu + tot_dev,
                    var,
                    mu + hfa / 2 + x[h] + x[N + a],
                    mu - hfa / 2 + x[a] + x[N + h],
                    hfa,
                    float(x[h]),
                    float(x[N + a]),
                    float(x[a]),
                    float(x[N + h]),
                )
            )
        for r in batch.itertuples(index=False):
            if not r.played:
                continue
            h, a = IDX[r.home_team], IDX[r.away_team]
            hfa = 0.0 if r.neutral else params.hfa
            for i, j, y, base in (
                (h, N + a, r.home_score, mu + hfa / 2),
                (a, N + h, r.away_score, mu - hfa / 2),
            ):
                ph = P[:, i] + P[:, j]
                s = ph[i] + ph[j] + s2
                k = ph / s
                x += k * (y - (base + x[i] + x[j]))
                P -= np.outer(k, ph)
            pts_sum += r.home_score + r.away_score
            pts_n += 2
    df = pd.DataFrame(
        out,
        columns=[
            "game_id",
            "kf_margin",
            "kf_total",
            "kf_var",
            "kf_pts_h",
            "kf_pts_a",
            "kf_hfa",
            "kf_h_off",
            "kf_a_def",
            "kf_a_off",
            "kf_h_def",
        ],
    )
    df["kf_sd"] = np.sqrt(df["kf_var"])
    df["kf_prob"] = ndtr(df["kf_margin"] / df["kf_sd"])
    return df


def _neg_loglik(theta: np.ndarray, games: pd.DataFrame, first_eval: int, until: int) -> float:
    p = _from_theta(theta)
    kf = run_kf(games, p, until_season=until)
    d = kf.merge(games[["game_id", "season", "result", "played"]], on="game_id")
    d = d[(d["season"] >= first_eval) & d["played"]]
    z = (d["result"] - d["kf_margin"]) / d["kf_sd"]
    return float(np.mean(0.5 * z**2 + np.log(d["kf_sd"])))


def _to_theta(p: KFParams) -> np.ndarray:
    return np.array(
        [np.log(p.q), np.log(p.s0), np.log(p.rho / (1 - p.rho)), p.hfa, np.log(p.sigma)]
    )


def _from_theta(t: np.ndarray) -> KFParams:
    return KFParams(
        q=float(np.clip(np.exp(t[0]), 0.005, 0.5)),
        s0=float(np.clip(np.exp(t[1]), 0.1, 8.0)),
        rho=float(np.clip(1 / (1 + np.exp(-t[2])), 0.4, 0.95)),
        hfa=float(np.clip(t[3], 0.0, 4.0)),
        sigma=float(np.clip(np.exp(t[4]), 7.5, 11.0)),
    )


def tune(
    games: pd.DataFrame,
    before_season: int,
    start: KFParams | None = None,
    first_eval: int = 2016,
    maxiter: int = 45,
) -> KFParams:
    """Maximum-likelihood hyper-parameters using only seasons < ``before_season``."""
    start = start or KFParams()
    sub = games[games["season"] < before_season]
    res = minimize(
        _neg_loglik,
        _to_theta(start),
        args=(sub, first_eval, before_season - 1),
        method="Nelder-Mead",
        options={"maxiter": maxiter, "xatol": 1e-2, "fatol": 1e-4},
    )
    return _from_theta(res.x)
