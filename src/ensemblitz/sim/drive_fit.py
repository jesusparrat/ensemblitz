"""Drive-outcome rates from nflverse, strict walk-forward.

A drive is one of TD, field goal, punt, turnover (including a miss or downs) or
end of half. Counts shrink toward the 2015-2016 league mix. The opponent
adjustment is additive on the log scale and then renormalised. Nothing here
reads the week being predicted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz.data.stadiums import HOME_STADIUMS

TEAMS = tuple(sorted(HOME_STADIUMS))
TEAM_INDEX = {t: i for i, t in enumerate(TEAMS)}
OUTCOMES = ("td", "fg", "punt", "to", "eoh")
N_OUT = 5
N_SCRIPT = 3  # trailing by 7+, within 6, leading by 7+
# 2015-2016 regular season, all drives. Shrinkage target for every later week.
PRIOR = np.array([0.2019, 0.1394, 0.3883, 0.1791, 0.0914])
PRIOR_SEC = np.array([145.0, 150.0, 148.0])
K_DRIVES = 70.0
K_SEC = 40.0
WEEK_DECAY = 0.997
SEASON_DECAY = 0.50
PROC = C.PROC_DIR / "pbp_sim" / "drives.parquet"
# Home TD rate minus away TD rate, 2015-2016, as a log-odds split. Neutral games add none.
HFA_TD_LOGIT = 0.07


def _fix(s: pd.Series) -> pd.Series:
    return s.replace(C.TEAM_FIX)


def drives_from_pbp(raw: pd.DataFrame) -> pd.DataFrame:
    """One row per offensive drive."""
    df = raw[raw["season_type"].isin(["REG", "POST"])].copy()
    for col in ("posteam", "defteam", "home_team", "away_team", "td_team"):
        if col in df.columns:
            df[col] = _fix(df[col])
    df = df[df["posteam"].notna() & df["fixed_drive"].notna()]
    df = df.sort_values(["game_id", "play_id"])
    prev_gs = df.groupby("game_id", sort=False)["game_seconds_remaining"].shift(1)
    prev_q = df.groupby("game_id", sort=False)["qtr"].shift(1)
    prev_fd = df.groupby("game_id", sort=False)["fixed_drive"].shift(1)
    elapsed = np.where(
        (df["qtr"] == prev_q) & (df["fixed_drive"] == prev_fd),
        (prev_gs - df["game_seconds_remaining"]).clip(lower=0, upper=90),
        0.0,
    )
    td = (df["touchdown"].eq(1) & df["td_team"].eq(df["posteam"])).astype(np.int8)
    fg = df["field_goal_result"].eq("made").astype(np.int8)
    punt = df["play_type"].eq("punt").astype(np.int8)
    turnover = (
        df["interception"].eq(1)
        | df["fumble_lost"].eq(1)
        | df["field_goal_result"].isin(["missed", "blocked"])
        | (
            (df["down"] == 4)
            & df["play_type"].isin(["pass", "run"])
            & df["first_down"].ne(1)
            & df["touchdown"].ne(1)
        )
    ).astype(np.int8)
    scr = df["play_type"].isin(["pass", "run", "qb_kneel", "qb_spike"]).astype(np.int16)
    tmp = pd.DataFrame(
        {
            "season": df["season"].to_numpy(),
            "week": df["week"].to_numpy(),
            "game_id": df["game_id"].to_numpy(),
            "fixed_drive": df["fixed_drive"].to_numpy(),
            "team": df["posteam"].to_numpy(),
            "opp": df["defteam"].to_numpy(),
            "home": df["home_team"].to_numpy(),
            "td": td.to_numpy(),
            "fg": fg.to_numpy(),
            "punt": punt.to_numpy(),
            "to": turnover.to_numpy(),
            "sec": elapsed,
            "plays": scr.to_numpy(),
            "diff": df["score_differential"].to_numpy(),
        }
    )
    ag = tmp.groupby(["season", "week", "game_id", "fixed_drive", "team"], as_index=False).agg(
        opp=("opp", "first"),
        home=("home", "first"),
        td=("td", "max"),
        fg=("fg", "max"),
        punt=("punt", "max"),
        to=("to", "max"),
        sec=("sec", "sum"),
        plays=("plays", "sum"),
        diff=("diff", "first"),
    )
    # TD, then FG, then turnover, then punt, otherwise the half ran out.
    out = np.full(len(ag), 4, np.int8)
    out = np.where(ag["punt"].to_numpy() == 1, 2, out)
    out = np.where(ag["to"].to_numpy() == 1, 3, out)
    out = np.where(ag["fg"].to_numpy() == 1, 1, out)
    out = np.where(ag["td"].to_numpy() == 1, 0, out)
    ag["out"] = out
    diff = ag["diff"].fillna(0).to_numpy()
    ag["script"] = np.where(diff <= -7, 0, np.where(diff >= 7, 2, 1)).astype(np.int8)
    ag["is_home"] = ag["team"].eq(ag["home"]).astype(np.int8)
    return ag[
        ["season", "week", "game_id", "team", "opp", "script", "out", "sec", "plays", "is_home"]
    ]


def build_drives(force: bool = False) -> pd.DataFrame:
    if PROC.exists() and not force:
        return pd.read_parquet(PROC)
    frames = []
    for season in range(C.FIRST_SEASON, C.LAST_BACKTEST_SEASON + 1):
        path = C.RAW_DIR / f"pbp_sim_{season}.parquet"
        if not path.exists():
            raise FileNotFoundError(path)
        frames.append(drives_from_pbp(pd.read_parquet(path)))
    out = pd.concat(frames, ignore_index=True)
    PROC.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(PROC, index=False)
    return out


@dataclass
class _Acc:
    off: np.ndarray  # (team, script, outcome) counts
    de: np.ndarray
    sec: np.ndarray  # (team, script) sum of seconds
    nsec: np.ndarray
    home_td: float = 0.0
    home_n: float = 0.0
    away_td: float = 0.0
    away_n: float = 0.0

    @classmethod
    def fresh(cls) -> _Acc:
        z = np.zeros((len(TEAMS), N_SCRIPT, N_OUT))
        return cls(
            off=z.copy(),
            de=z.copy(),
            sec=np.zeros((len(TEAMS), N_SCRIPT)),
            nsec=np.zeros((len(TEAMS), N_SCRIPT)),
        )

    def decay_week(self) -> None:
        self.off *= WEEK_DECAY
        self.de *= WEEK_DECAY
        self.sec *= WEEK_DECAY
        self.nsec *= WEEK_DECAY

    def decay_season(self) -> None:
        self.decay_week()
        self.off *= SEASON_DECAY / WEEK_DECAY
        self.de *= SEASON_DECAY / WEEK_DECAY
        self.sec *= SEASON_DECAY / WEEK_DECAY
        self.nsec *= SEASON_DECAY / WEEK_DECAY
        self.home_td *= SEASON_DECAY
        self.home_n *= SEASON_DECAY
        self.away_td *= SEASON_DECAY
        self.away_n *= SEASON_DECAY


class DriveBook:
    """Walk-forward drive counts. ``advance_to`` keeps only earlier weeks."""

    def __init__(self, drives: pd.DataFrame):
        self.drives = drives
        self.acc = _Acc.fresh()
        self._weeks = {key: g for key, g in drives.groupby(["season", "week"], sort=False)}

    def advance_to(self, season: int, week: int) -> None:
        self.acc = _Acc.fresh()
        prev = 0
        for (s, w), g in sorted(self._weeks.items()):
            if (int(s), int(w)) >= (season, week):
                break
            if prev and int(s) != prev:
                self.acc.decay_season()
            self.acc.decay_week()
            self._add(g)
            prev = int(s)

    def _add(self, g: pd.DataFrame) -> None:
        if g.empty:
            return
        off_i = g["team"].map(TEAM_INDEX)
        def_i = g["opp"].map(TEAM_INDEX)
        ok = off_i.notna() & def_i.notna()
        g = g.loc[ok]
        off_i = off_i[ok].astype(int).to_numpy()
        def_i = def_i[ok].astype(int).to_numpy()
        script = g["script"].to_numpy(int)
        out = g["out"].to_numpy(int)
        np.add.at(self.acc.off, (off_i, script, out), 1.0)
        np.add.at(self.acc.de, (def_i, script, out), 1.0)
        np.add.at(self.acc.sec, (off_i, script), g["sec"].to_numpy(float))
        np.add.at(self.acc.nsec, (off_i, script), 1.0)
        home = g["is_home"].to_numpy() == 1
        self.acc.home_td += float(((g["out"] == 0) & home).sum())
        self.acc.home_n += float(home.sum())
        self.acc.away_td += float(((g["out"] == 0) & ~home).sum())
        self.acc.away_n += float((~home).sum())

    def hfa_logit(self) -> float:
        if self.acc.home_n < 80 or self.acc.away_n < 80:
            return HFA_TD_LOGIT
        ph = (self.acc.home_td + 20 * PRIOR[0]) / (self.acc.home_n + 20)
        pa = (self.acc.away_td + 20 * PRIOR[0]) / (self.acc.away_n + 20)
        ph = float(np.clip(ph, 0.05, 0.45))
        pa = float(np.clip(pa, 0.05, 0.45))
        return 0.5 * (np.log(ph / (1 - ph)) - np.log(pa / (1 - pa)))

    def mix(self, idx: np.ndarray, kind: str) -> np.ndarray:
        """(n, script, outcome) probabilities for the indexed teams."""
        counts = self.acc.off if kind == "off" else self.acc.de
        taken = counts[idx]  # (n, script, 5)
        league = counts.sum(axis=0)  # (script, 5)
        league_p = (league + K_DRIVES * PRIOR) / (league.sum(axis=1, keepdims=True) + K_DRIVES)
        tot = taken.sum(axis=2, keepdims=True)
        return (taken + K_DRIVES * league_p) / (tot + K_DRIVES)

    def seconds(self, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n = self.acc.nsec[idx]
        sec = self.acc.sec[idx]
        league_n = self.acc.nsec.sum(axis=0)
        league_s = self.acc.sec.sum(axis=0)
        league_mean = (league_s + K_SEC * PRIOR_SEC) / (league_n + K_SEC)
        mean = (sec + K_SEC * league_mean) / (n + K_SEC)
        return mean, np.full_like(mean, 48.0)


def rates_before(drives: pd.DataFrame, season: int, week: int) -> DriveBook:
    book = DriveBook(drives)
    book.advance_to(season, week)
    return book


def load_drives() -> pd.DataFrame:
    if not PROC.exists():
        return build_drives()
    return pd.read_parquet(PROC)


def prior_check(path: Path | None = None) -> dict:
    """Write the 2015-2016 mix next to the cache so the constant above can be audited."""
    drives = load_drives()
    early = drives[drives["season"] < 2017]
    share = early["out"].value_counts(normalize=True).reindex(range(5)).fillna(0)
    payload = {
        "seasons": "2015-2016",
        "share": [round(float(x), 4) for x in share],
        "labels": list(OUTCOMES),
    }
    dest = path or (PROC.parent / "drive_prior.json")
    dest.write_text(json.dumps(payload, indent=1) + "\n")
    return payload
