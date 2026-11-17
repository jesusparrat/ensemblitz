"""Player value table: how many points of margin per game a player is worth over a replacement.

Built from nflverse weekly player stats and snap counts of the current season (weight 1) and the
previous one (weight 0.5). Cheap: two small downloads and a few group-bys.

Units: *points of team margin per game, versus a replacement-level player*, then scaled by
``CONSERVATIVE`` (volume moves to teammates, EPA is noisy, teams adapt).

Offence, from player EPA (efficiency shrunk towards the position mean, volume per game played):
    QB   volume = dropbacks + carries,  eff = (pass EPA + rush EPA) / volume,  prior 150 plays
    RB   volume = carries + targets,    eff = (rush EPA + rec EPA) / volume,   prior 80 touches
    WR/TE volume = targets,             eff = rec EPA / target,                prior 40 targets
    value = volume_per_game * (eff_shrunk - replacement_eff)
    replacement_eff = pooled efficiency of low-volume players at the position (backups).
Offensive line: no individual stats exist, so snap share x a position prior (0.9 pts per starter).
Defence: no EPA at player level in free data, so value = position prior x snap-share factor x a
production index (sacks, hits, TFL, INT, PD per game relative to starters at the position, shrunk
with 4 pseudo-games and clipped to 0.6-1.8). Position priors are judgement, not fitted:
    EDGE 1.3 | CB 0.9 | DT 0.8 | LB 0.6 | S 0.6   (points per game of a starter)
Kickers, punters and long snappers are not valued.
"""

from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

CONSERVATIVE = 0.7
PRIOR_PTS = {"EDGE": 1.3, "CB": 0.9, "DT": 0.8, "LB": 0.6, "S": 0.6, "OL": 0.9}
CAPS = {
    "QB": 7.0,
    "RB": 1.8,
    "WR": 2.5,
    "TE": 1.5,
    "EDGE": 3.0,
    "CB": 2.0,
    "DT": 1.8,
    "LB": 1.4,
    "S": 1.4,
    "OL": 1.0,
}
EFF_PRIOR = {"QB": 150.0, "RB": 80.0, "WR": 40.0, "TE": 40.0}
GROUPS = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "HB": "RB",
    "WR": "WR",
    "TE": "TE",
    "T": "OL",
    "G": "OL",
    "C": "OL",
    "OL": "OL",
    "OT": "OL",
    "OG": "OL",
    "DE": "EDGE",
    "EDGE": "EDGE",
    "OLB": "EDGE",
    "DT": "DT",
    "NT": "DT",
    "DL": "DT",
    "LB": "LB",
    "ILB": "LB",
    "MLB": "LB",
    "CB": "CB",
    "S": "S",
    "FS": "S",
    "SS": "S",
    "DB": "S",
}
SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def norm_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", " ", s.replace("'", ""))
    return re.sub(r"\s+", " ", SUFFIX.sub(" ", s)).strip()


def _group(pos: pd.Series) -> pd.Series:
    return pos.astype(str).str.upper().map(GROUPS)


def _shrink(total: float, vol: float, mean: float, k: float) -> float:
    return (total + k * mean) / (vol + k)


def load_raw(season: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    import nflreadpy as nfl

    seasons = [season - 1, season]
    return (
        nfl.load_player_stats(seasons).to_pandas(),
        nfl.load_snap_counts(seasons).to_pandas(),
    )


def build_values(stats: pd.DataFrame, snaps: pd.DataFrame, season: int) -> pd.DataFrame:
    """One row per (player, position group) with ``value_pts`` (>= 0)."""
    w = lambda s: np.where(s == season, 1.0, 0.5)  # noqa: E731
    sn = snaps[snaps["game_type"] == "REG"].copy()
    sn["group"] = _group(sn["position"])
    sn = sn.dropna(subset=["group"])
    sn["key"] = sn["player"].map(norm_name) + "|" + sn["group"]
    sn["w"] = w(sn["season"])
    sn["pct"] = sn[["offense_pct", "defense_pct"]].max(axis=1)
    sn["played"] = (sn["pct"] >= 0.25) * sn["w"]
    sn["off_w"] = sn["offense_pct"].fillna(0) * sn["w"]
    sn["def_w"] = sn["defense_pct"].fillna(0) * sn["w"]
    sg = sn.groupby("key").agg(
        games=("played", "sum"),
        wsum=("w", "sum"),
        off_w=("off_w", "sum"),
        def_w=("def_w", "sum"),
        team=("team", "last"),
        name=("player", "last"),
    )
    sg["avg_off"] = sg["off_w"] / sg["wsum"].clip(lower=1e-9)
    sg["avg_def"] = sg["def_w"] / sg["wsum"].clip(lower=1e-9)
    sg["group"] = [k.split("|")[1] for k in sg.index]

    st = stats[stats["season_type"] == "REG"].copy()
    st["group"] = _group(st["position"])
    st = st.dropna(subset=["group"])
    st["key"] = st["player_display_name"].map(norm_name) + "|" + st["group"]
    st["w"] = w(st["season"])
    cols = [
        "attempts",
        "sacks_suffered",
        "passing_epa",
        "carries",
        "rushing_epa",
        "targets",
        "receiving_epa",
        "def_sacks",
        "def_qb_hits",
        "def_tackles_for_loss",
        "def_fumbles_forced",
        "def_interceptions",
        "def_pass_defended",
        "def_tackles_solo",
        "def_tackle_assists",
    ]
    for c in cols:
        st[c] = st[c].fillna(0) * st["w"]
    ag = st.groupby("key")[cols].sum()
    df = sg.join(ag, how="left").fillna(0.0)
    df["games"] = df["games"].clip(lower=0)
    df["value_pts"] = 0.0
    df["method"] = ""

    _offense_epa(df)
    _line_snaps(df)
    _defense_production(df)
    df["value_pts"] = df["value_pts"].clip(lower=0)
    for g, cap in CAPS.items():
        m = df["group"] == g
        df.loc[m, "value_pts"] = df.loc[m, "value_pts"].clip(upper=cap)
    df["value_pts"] = df["value_pts"].round(3)
    out = df.reset_index().rename(columns={"index": "key"})
    return out[
        ["key", "name", "team", "group", "games", "avg_off", "avg_def", "value_pts", "method"]
    ]


def _offense_epa(df: pd.DataFrame) -> None:
    spec = {
        "QB": (
            df["attempts"] + df["sacks_suffered"] + df["carries"],
            df["passing_epa"] + df["rushing_epa"],
        ),
        "RB": (df["carries"] + df["targets"], df["rushing_epa"] + df["receiving_epa"]),
        "WR": (df["targets"], df["receiving_epa"]),
        "TE": (df["targets"], df["receiving_epa"]),
    }
    for g, (vol, epa) in spec.items():
        m = (df["group"] == g) & (df["games"] >= 2) & (vol > 0)
        if m.sum() < 5:
            continue
        # replacement = pooled efficiency of the low-volume half (backups, fringe players)
        low = m & (vol <= vol[m].median())
        repl = epa[low].sum() / max(vol[low].sum(), 1.0)
        mean = epa[m].sum() / vol[m].sum()
        for key in df.index[m]:
            eff = _shrink(epa[key], vol[key], mean, EFF_PRIOR[g])
            per_game = vol[key] / max(df.at[key, "games"], 1.0)
            df.at[key, "value_pts"] = CONSERVATIVE * per_game * (eff - repl)
            df.at[key, "method"] = "EPA vs replacement"


def _line_snaps(df: pd.DataFrame) -> None:
    m = df["group"] == "OL"
    share = (df.loc[m, "avg_off"] / 0.9).clip(0, 1)
    sample = (df.loc[m, "games"] / 6.0).clip(0, 1)
    df.loc[m, "value_pts"] = PRIOR_PTS["OL"] * share * sample
    df.loc[m, "method"] = "snap share x prior"


def _defense_production(df: pd.DataFrame) -> None:
    tk = df["def_tackles_solo"] + df["def_tackle_assists"]
    score = {
        "EDGE": df["def_sacks"]
        + 0.35 * df["def_qb_hits"]
        + 0.5 * df["def_tackles_for_loss"]
        + 0.6 * df["def_fumbles_forced"],
        "DT": df["def_sacks"]
        + 0.35 * df["def_qb_hits"]
        + 0.5 * df["def_tackles_for_loss"]
        + 0.6 * df["def_fumbles_forced"],
        "LB": 0.9 * df["def_sacks"]
        + 0.5 * df["def_tackles_for_loss"]
        + 0.5 * df["def_pass_defended"]
        + df["def_interceptions"]
        + 0.3 * df["def_fumbles_forced"]
        + 0.08 * tk,
        "CB": df["def_interceptions"]
        + 0.35 * df["def_pass_defended"]
        + 0.5 * df["def_tackles_for_loss"]
        + 0.05 * tk,
        "S": df["def_interceptions"]
        + 0.35 * df["def_pass_defended"]
        + 0.5 * df["def_tackles_for_loss"]
        + 0.05 * tk,
    }
    for g, sc in score.items():
        m = df["group"] == g
        starters = m & (df["avg_def"] >= 0.5) & (df["games"] >= 3)
        if starters.sum() < 5:
            continue
        mean_pg = (sc[starters] / df.loc[starters, "games"]).mean()
        for key in df.index[m]:
            games = df.at[key, "games"]
            idx = _shrink(sc[key], games, mean_pg, 4.0) / max(mean_pg, 1e-9)
            idx = float(np.clip(idx**0.6, 0.6, 1.8))
            share = float(np.clip(df.at[key, "avg_def"] / 0.75, 0, 1))
            sample = min(games / 6.0, 1.0)
            df.at[key, "value_pts"] = PRIOR_PTS[g] * share * idx * sample
            df.at[key, "method"] = "snap share x prior x production"


def lookup(values: pd.DataFrame, name: str, position: str | None) -> pd.Series | None:
    """Find a player by name (and position group when given); the best-valued match wins."""
    n = norm_name(name)
    grp = GROUPS.get((position or "").upper())
    keys = values["key"]
    m = keys.str.startswith(n + "|")
    if grp:
        m &= keys.str.endswith("|" + grp)
    hit = values[m]
    return None if hit.empty else hit.sort_values("value_pts", ascending=False).iloc[0]
