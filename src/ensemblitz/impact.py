"""Per-player injury impact in spread points, strictly walk-forward.

For a game in (season, week) every number comes from records *before* that week:

* ``value_table``  points of team margin per game a player is worth over a replacement,
                   from decayed (half-life ``HALF_LIFE`` weeks) EPA, snap shares and production of
                   earlier games only. Same formulas as ``players.py`` (which is a snapshot for
                   live news), but as-of any past week so it can be backtested.
* ``Availability`` probability of playing given the Friday label, the practice status and the
                   position, estimated from earlier weeks' reports and snap counts only.
* ``injury_features`` expected points lost per team and group: sum of p(miss) x value.

The scale of each group is not trusted: ``phase1.py`` fits it walk-forward (ridge towards a
prior), so a badly calibrated prior shows up as a small coefficient instead of a wrong forecast.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz import players as PL

HALF_LIFE = 24.0  # weeks (about 1.3 seasons)
MAX_AGE = 5 * HALF_LIFE
WEEKS_PER_SEASON = 18
SEASON0 = 2015
EXTRA_GROUPS = {"SAF": "S", "DB": "S", "OT": "OL", "OG": "OL"}
GROUP_OF = {**PL.GROUPS, **EXTRA_GROUPS}
CAPS = {**PL.CAPS, "QB": 10.0}  # the beta fit rescales; a higher QB cap keeps stars apart
BETA_GROUPS = ["QB", "SKILL", "OL", "FRONT", "SECONDARY"]
BETA_OF = {
    "QB": "QB",
    "RB": "SKILL",
    "WR": "SKILL",
    "TE": "SKILL",
    "OL": "OL",
    "EDGE": "FRONT",
    "DT": "FRONT",
    "LB": "FRONT",
    "CB": "SECONDARY",
    "S": "SECONDARY",
}
STAT_COLS = [
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
PRACTICE = {
    "Full Participation in Practice": "full",
    "Limited Participation in Practice": "limited",
    "Did Not Participate In Practice": "dnp",
    "Out (Definitely Will Not Play)": "dnp",
}
LABELS = {"Out", "Doubtful", "Questionable", "Probable"}


def tau(season: pd.Series | int, week: pd.Series | int):
    """Monotone week index used for decay and walk-forward cut-offs."""
    return (season - SEASON0) * WEEKS_PER_SEASON + week


def group_of(position: pd.Series) -> pd.Series:
    return position.astype(str).str.upper().map(GROUP_OF)


# ------------------------------------------------------------------ data
def load_inputs() -> dict[str, pd.DataFrame]:
    r = C.RAW_DIR
    return {
        "stats": pd.read_parquet(r / "player_stats.parquet"),
        "snaps": pd.read_parquet(r / "snap_counts.parquet"),
        "ids": pd.read_parquet(r / "player_ids.parquet"),
        "inj": pd.read_parquet(r / "injuries.parquet"),
    }


def player_games(stats: pd.DataFrame, snaps: pd.DataFrame, ids: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, season, week) with stats, snap shares, group and week index."""
    st = stats[stats["season_type"] == "REG"].copy()
    st["gsis"] = st["player_id"]
    st["group"] = group_of(st["position"])
    sn = snaps[snaps["game_type"] == "REG"].merge(
        ids.rename(columns={"gsis_id": "gsis", "pfr_id": "pfr_player_id"}),
        on="pfr_player_id",
        how="inner",
    )
    sn["sgroup"] = group_of(sn["position"])
    sn["off_pct"] = sn["offense_pct"].fillna(0.0)
    sn["def_pct"] = sn["defense_pct"].fillna(0.0)
    sn = sn[["gsis", "season", "week", "off_pct", "def_pct", "sgroup"]].drop_duplicates(
        ["gsis", "season", "week"]
    )
    st = st[["gsis", "season", "week", "group", *STAT_COLS]].drop_duplicates(
        ["gsis", "season", "week"]
    )
    pg = st.merge(sn, on=["gsis", "season", "week"], how="outer")
    pg["group"] = pg["group"].fillna(pg["sgroup"])
    pg = pg.drop(columns="sgroup").dropna(subset=["group"])
    for c in STAT_COLS:
        pg[c] = pg[c].fillna(0.0)
    has_snap = pg[["off_pct", "def_pct"]].notna().any(axis=1)
    pct = pg[["off_pct", "def_pct"]].max(axis=1)
    usage = pg[["attempts", "carries", "targets", "def_tackles_solo", "def_tackle_assists"]].sum(
        axis=1
    )
    pg["played"] = np.where(has_snap, pct >= 0.25, usage >= 1).astype(float)
    pg["off_pct"] = pg["off_pct"].fillna(0.0)
    pg["def_pct"] = pg["def_pct"].fillna(0.0)
    pg["tau"] = tau(pg["season"], pg["week"])
    return pg.sort_values("tau").reset_index(drop=True)


# ------------------------------------------------------------------ player value as of a week
def value_table(pg: pd.DataFrame, tau0: int) -> pd.DataFrame:
    """Value over replacement (spread points per game, >= 0) using only weeks before ``tau0``."""
    sub = pg[(pg["tau"] < tau0) & (pg["tau"] >= tau0 - MAX_AGE)]
    if sub.empty:
        return pd.DataFrame(columns=["group", "value_pts"])
    w = np.power(0.5, (tau0 - sub["tau"].to_numpy()) / HALF_LIFE)
    cols = [*STAT_COLS, "off_pct", "def_pct", "played"]
    wd = sub[cols].mul(w, axis=0)
    wd["wsum"] = w
    wd["gsis"] = sub["gsis"].to_numpy()
    ag = wd.groupby("gsis").sum()
    # snap shares are averaged over the games the player has a row in (as in players.py)
    ag["avg_off"] = ag["off_pct"] / ag["wsum"].clip(lower=1e-9)
    ag["avg_def"] = ag["def_pct"] / ag["wsum"].clip(lower=1e-9)
    ag["games"] = ag["played"]
    ag["group"] = sub.groupby("gsis")["group"].last()
    ag["value_pts"] = 0.0
    PL._offense_epa(ag)
    PL._line_snaps(ag)
    PL._defense_production(ag)
    ag["value_pts"] = ag["value_pts"].clip(lower=0)
    for g, cap in CAPS.items():
        m = ag["group"] == g
        ag.loc[m, "value_pts"] = ag.loc[m, "value_pts"].clip(upper=cap)
    return ag[["group", "value_pts"]]


# ------------------------------------------------------------------ availability
def injury_rows(inj: pd.DataFrame, snaps: pd.DataFrame, ids: pd.DataFrame) -> pd.DataFrame:
    """Injury report rows (REG weeks) with the practice category and whether the player played."""
    d = inj[inj["week"] <= WEEKS_PER_SEASON].copy()
    d["team"] = d["team"].replace(C.TEAM_FIX)
    d["label"] = d["report_status"].where(d["report_status"].isin(LABELS))
    d["practice"] = d["practice_status"].map(PRACTICE).fillna("unknown")
    d["group"] = group_of(d["position"])
    # no label and a full practice: not an injury, expected to play like anyone else
    d["listed"] = d["label"].notna() | d["practice"].isin(["limited", "dnp"])
    sn = snaps[snaps["game_type"] == "REG"].merge(
        ids.rename(columns={"gsis_id": "gsis", "pfr_id": "pfr_player_id"}),
        on="pfr_player_id",
        how="inner",
    )
    sn["any_snap"] = sn[["offense_snaps", "defense_snaps", "st_snaps"]].fillna(0).sum(axis=1) > 0
    played = sn[sn["any_snap"]][["season", "week", "gsis"]].drop_duplicates()
    played["played"] = 1.0
    d = d.merge(
        played.rename(columns={"gsis": "gsis_id"}), on=["season", "week", "gsis_id"], how="left"
    )
    weeks_with_snaps = sn[["season", "week"]].drop_duplicates().assign(snaps_known=True)
    d = d.merge(weeks_with_snaps, on=["season", "week"], how="left")
    d["snaps_known"] = d["snaps_known"].fillna(False).astype(bool)
    d["played"] = d["played"].fillna(0.0)
    d["tau"] = tau(d["season"], d["week"])
    return d.drop_duplicates(["season", "week", "gsis_id"])


class Availability:
    """P(player plays | label, practice, group), shrunk hierarchically, from earlier weeks only."""

    def __init__(self, rows: pd.DataFrame, tau0: int, strength: float = 20.0) -> None:
        h = rows[(rows["tau"] < tau0) & rows["snaps_known"] & rows["listed"]]
        h = h.assign(label=h["label"].fillna("none"))
        self.m = strength
        self.base = float(h["played"].mean()) if len(h) else 0.9
        self.l1 = h.groupby("label")["played"].agg(["sum", "count"])
        self.l2 = h.groupby(["label", "practice"])["played"].agg(["sum", "count"])
        self.l3 = h.groupby(["label", "practice", "group"])["played"].agg(["sum", "count"])

    def _shrunk(self, tab: pd.DataFrame, key, parent: float) -> float:
        if key in tab.index:
            s, n = tab.loc[key, "sum"], tab.loc[key, "count"]
            return float((s + self.m * parent) / (n + self.m))
        return parent

    def p_play(self, label: str, practice: str, group: str) -> float:
        p1 = self._shrunk(self.l1, label, self.base)
        p2 = self._shrunk(self.l2, (label, practice), p1)
        return self._shrunk(self.l3, (label, practice, group), p2)


# ------------------------------------------------------------------ expected points lost per team
def injury_features(
    games: pd.DataFrame,
    pg: pd.DataFrame,
    rows: pd.DataFrame,
    first_season: int = C.WARMUP_SEASON,
    last_season: int = C.LAST_BACKTEST_SEASON,
) -> pd.DataFrame:
    """Per game: expected points lost by home and away for each beta group (and a binary twin).

    ``games`` needs game_id, season, week, home_team, away_team. Columns: ``h_<G>``, ``a_<G>``
    (probability-weighted) and ``hb_<G>``, ``ab_<G>`` (Out/Doubtful counted as a certain miss).
    """
    out = []
    listed = rows[rows["listed"]]
    for (season, week), gm in games.groupby(["season", "week"], sort=True):
        if season < first_season or season > last_season or week > WEEKS_PER_SEASON:
            continue
        t0 = int(tau(season, week))
        vt = value_table(pg, t0)
        av = Availability(rows, t0)
        wk = listed[(listed["season"] == season) & (listed["week"] == week)].copy()
        wk = wk.join(vt, on="gsis_id", how="left", rsuffix="_stat")
        wk["grp"] = wk["group_stat"].fillna(wk["group"])
        wk = wk[wk["grp"].isin(BETA_OF)]
        wk["value_pts"] = wk["value_pts"].fillna(0.0)
        wk["p_miss"] = [
            1.0 - av.p_play(lab if isinstance(lab, str) else "none", pr, g)
            for lab, pr, g in zip(wk["label"], wk["practice"], wk["grp"], strict=True)
        ]
        wk["p_bin"] = wk["label"].isin(["Out", "Doubtful"]).astype(float)
        wk["bg"] = wk["grp"].map(BETA_OF)
        wk["x"] = wk["p_miss"] * wk["value_pts"]
        wk["xb"] = wk["p_bin"] * wk["value_pts"]
        agg = wk.groupby(["team", "bg"])[["x", "xb"]].sum()
        for g in gm.itertuples(index=False):
            rec = {"game_id": g.game_id}
            for side, team in (("h", g.home_team), ("a", g.away_team)):
                for bg in BETA_GROUPS:
                    key = (team, bg)
                    rec[f"{side}_{bg}"] = float(agg.at[key, "x"]) if key in agg.index else 0.0
                    rec[f"{side}b_{bg}"] = float(agg.at[key, "xb"]) if key in agg.index else 0.0
            out.append(rec)
    return pd.DataFrame(out)
