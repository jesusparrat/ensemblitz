"""Build the game-level feature table.

Rule that keeps this leakage-free: games are processed in (season, week) batches. Features of a
batch are computed from state built from *earlier* batches only; the state is updated with the
batch's results afterwards. Future (unplayed) games get features from the current state.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ensemblitz.data.stadiums import HOME_STADIUMS, haversine_km, venue_coords
from ensemblitz.features.ratings import DecayedMean, Elo

UNITS = ("pass", "rush", "sr")
HOME_ADV_ELO_PTS = 25.0  # Elo points per point of margin


@dataclass(frozen=True)
class FeatureParams:
    decay: float = 0.92  # per-game memory of team ratings
    season_keep: float = 0.55  # share of evidence kept across seasons
    prior_pass: float = 150.0  # pseudo plays of prior (regression to the mean)
    prior_rush: float = 100.0
    prior_sr: float = 150.0
    qb_decay: float = 0.97
    qb_prior: float = 200.0  # pseudo dropbacks
    qb_keep: float = 0.8


def _roof_dome(roof: object) -> int:
    return int(roof in ("dome", "closed"))


def build_features(
    games: pd.DataFrame,
    team_games: pd.DataFrame,
    qb_games: pd.DataFrame,
    injuries: pd.DataFrame | None = None,
    params: FeatureParams | None = None,
) -> pd.DataFrame:
    """One row per game with pre-game features (home/away prefixed ``h_`` / ``a_``)."""
    fp = params or FeatureParams()
    games = games.sort_values(["season", "week", "kickoff_utc", "game_id"]).reset_index(drop=True)

    tg = {(r.game_id, r.team): r for r in team_games.itertuples(index=False)}
    qb_by_game: dict[str, list] = {}
    for r in qb_games.itertuples(index=False):
        qb_by_game.setdefault(r.game_id, []).append(r)
    inj = {}
    if injuries is not None and len(injuries):
        inj = {(r.season, r.week, r.team): r.n_out for r in injuries.itertuples(index=False)}

    prior = {"pass": fp.prior_pass, "rush": fp.prior_rush, "sr": fp.prior_sr}
    off = {u: DecayedMean(fp.decay, prior[u]) for u in UNITS}
    dfn = {u: DecayedMean(fp.decay, prior[u]) for u in UNITS}
    qb_rate = DecayedMean(fp.qb_decay, fp.qb_prior)
    elo = Elo()
    last_qb: dict[str, str] = {}

    rows: list[dict] = []
    cur_season = None
    for (season, _week), batch in games.groupby(["season", "week"], sort=True):
        if season != cur_season:
            if cur_season is not None:
                for m in (*off.values(), *dfn.values()):
                    m.new_season(fp.season_keep)
                qb_rate.new_season(fp.qb_keep)
                elo.new_season()
            cur_season = season

        for g in batch.itertuples(index=False):
            rows.append(_game_features(g, off, dfn, qb_rate, elo, last_qb, inj))

        # ---- update state with the batch results (played games only) ----
        for g in batch.itertuples(index=False):
            if not g.played:
                continue
            _update_state(g, tg, qb_by_game, off, dfn, qb_rate, elo, last_qb)
    return pd.DataFrame(rows)


def _game_features(g, off, dfn, qb_rate, elo, last_qb, inj) -> dict:
    h, a = g.home_team, g.away_team
    neutral = bool(g.neutral)
    f: dict = {
        "game_id": g.game_id,
        "season": g.season,
        "week": g.week,
        "home_team": h,
        "away_team": a,
        "kickoff_utc": g.kickoff_utc,
        "played": bool(g.played),
        "neutral": int(neutral),
        "div_game": int(g.div_game) if pd.notna(g.div_game) else 0,
    }
    # --- opponent-aware EPA / success ratings -------------------------------------------------
    for u in UNITS:
        f[f"h_off_{u}"], f[f"a_off_{u}"] = off[u].value(h), off[u].value(a)
        f[f"h_def_{u}"], f[f"a_def_{u}"] = dfn[u].value(h), dfn[u].value(a)
        f[f"h_vs_a_{u}"] = f[f"h_off_{u}"] - f[f"a_def_{u}"]  # home offence vs away defence
        f[f"a_vs_h_{u}"] = f[f"a_off_{u}"] - f[f"h_def_{u}"]
        f[f"net_{u}"] = f[f"h_vs_a_{u}"] - f[f"a_vs_h_{u}"]
    # --- Elo ----------------------------------------------------------------------------------
    f["elo_h"], f["elo_a"] = elo.r[h], elo.r[a]
    f["elo_diff"] = elo.diff(h, a, neutral)
    f["elo_prob"] = 1.0 / (1.0 + 10 ** (-f["elo_diff"] / 400.0))
    f["elo_margin"] = f["elo_diff"] / HOME_ADV_ELO_PTS
    # --- quarterbacks -------------------------------------------------------------------------
    hq = g.home_qb_id if isinstance(g.home_qb_id, str) else last_qb.get(h)
    aq = g.away_qb_id if isinstance(g.away_qb_id, str) else last_qb.get(a)
    f["h_qb_rate"] = qb_rate.value(hq) if hq else 0.0
    f["a_qb_rate"] = qb_rate.value(aq) if aq else 0.0
    f["h_qb_exp"] = qb_rate.weight(hq) if hq else 0.0
    f["a_qb_exp"] = qb_rate.weight(aq) if aq else 0.0
    f["qb_diff"] = f["h_qb_rate"] - f["a_qb_rate"]
    f["h_qb_change"] = int(bool(hq) and h in last_qb and hq != last_qb[h])
    f["a_qb_change"] = int(bool(aq) and a in last_qb and aq != last_qb[a])
    f["h_qb_id"], f["a_qb_id"] = hq, aq
    # --- rest and travel ----------------------------------------------------------------------
    hr = g.home_rest if pd.notna(g.home_rest) else 7
    ar = g.away_rest if pd.notna(g.away_rest) else 7
    f.update(
        h_rest=hr,
        a_rest=ar,
        rest_diff=hr - ar,
        h_short=int(hr <= 5),
        a_short=int(ar <= 5),
        h_bye=int(hr >= 13),
        a_bye=int(ar >= 13),
    )
    vlat, vlon = venue_coords(g.stadium_id, h, neutral)
    alat, alon = HOME_STADIUMS[a]
    hlat, hlon = HOME_STADIUMS[h]
    f["a_travel_km"] = haversine_km(alat, alon, vlat, vlon)
    f["h_travel_km"] = haversine_km(hlat, hlon, vlat, vlon) if neutral else 0.0
    f["a_tz_shift"] = (alon - vlon) / 15.0  # hours; positive = travelling west -> east
    f["h_tz_shift"] = (hlon - vlon) / 15.0 if neutral else 0.0
    # --- conditions ---------------------------------------------------------------------------
    dome = _roof_dome(g.roof)
    f["dome"] = dome
    f["temp"] = 70.0 if dome else (g.temp if pd.notna(g.temp) else 58.0)
    f["wind"] = 0.0 if dome else (g.wind if pd.notna(g.wind) else 7.0)
    # Not a model input: lets the site tell a real reading from the 58 F / 7 mph fill-in.
    f["weather_known"] = int(pd.notna(g.temp) and pd.notna(g.wind))
    f["turf"] = int(isinstance(g.surface, str) and "grass" not in g.surface and g.surface != "")
    # --- injuries reported the week(s) before (the current week's report is not out on Tuesday) -
    f["h_out_lag"] = _lag_inj(inj, g.season, g.week, h)
    f["a_out_lag"] = _lag_inj(inj, g.season, g.week, a)
    # --- market (kept in the frame; models decide whether to use it) --------------------------
    f["spread_line"] = g.spread_line
    f["total_line"] = g.total_line
    f["home_moneyline"] = g.home_moneyline
    f["away_moneyline"] = g.away_moneyline
    # --- targets (NaN for future games) -------------------------------------------------------
    f["result"] = g.result
    f["total"] = g.total
    f["home_score"] = g.home_score
    f["away_score"] = g.away_score
    return f


def _lag_inj(inj: dict, season: int, week: int, team: str) -> float:
    for lag in (1, 2):
        v = inj.get((season, week - lag, team))
        if v is not None:
            return float(v)
    return 0.0


def _update_state(g, tg, qb_by_game, off, dfn, qb_rate, elo, last_qb) -> None:
    h, a = g.home_team, g.away_team
    rows = {h: tg.get((g.game_id, h)), a: tg.get((g.game_id, a))}
    if rows[h] is not None and rows[a] is not None:
        # opponent adjustments use ratings *before* this game
        pre = {t: {u: (off[u].value(t), dfn[u].value(t)) for u in UNITS} for t in (h, a)}
        for t, o in ((h, a), (a, h)):
            r = rows[t]
            obs = {
                "pass": (r.epa_pass / r.n_pass if r.n_pass else 0.0, r.n_pass),
                "rush": (r.epa_rush / r.n_rush if r.n_rush else 0.0, r.n_rush),
                "sr": (
                    r.succ / (r.n_pass + r.n_rush) if r.n_pass + r.n_rush else 0.0,
                    r.n_pass + r.n_rush,
                ),
            }
            for u, (x, w) in obs.items():
                if u == "sr":
                    x -= 0.45  # centre success rate so the prior mean 0 means "league average"
                # defence ratings are "EPA allowed": a positive value is a bad defence
                off[u].update(t, x - pre[o][u][1], w)
                dfn[u].update(o, x - pre[t][u][0], w)
    for q in qb_by_game.get(g.game_id, []):
        if q.n_db:
            qb_rate.update(q.qb_id, q.epa_db / q.n_db, q.n_db)
    for t, qid in ((h, g.home_qb_id), (a, g.away_qb_id)):
        if isinstance(qid, str):
            last_qb[t] = qid
    if pd.notna(g.result):
        elo.update(h, a, float(g.result), bool(g.neutral))


def feature_columns(include_market: bool = False) -> list[str]:
    """Columns fed to the gradient boosting models."""
    cols = []
    for u in UNITS:
        cols += [f"h_vs_a_{u}", f"a_vs_h_{u}", f"net_{u}"]
    cols += [
        "elo_diff",
        "elo_prob",
        "h_qb_rate",
        "a_qb_rate",
        "qb_diff",
        "h_qb_exp",
        "a_qb_exp",
        "h_qb_change",
        "a_qb_change",
        "h_rest",
        "a_rest",
        "rest_diff",
        "h_bye",
        "a_bye",
        "a_travel_km",
        "a_tz_shift",
        "h_travel_km",
        "neutral",
        "div_game",
        "dome",
        "temp",
        "wind",
        "turf",
        "h_out_lag",
        "a_out_lag",
        "week",
        "kf_margin",
        "kf_total",
    ]
    if include_market:
        cols += ["spread_line", "total_line"]
    return cols


__all__ = ["FeatureParams", "build_features", "feature_columns", "np"]
