"""Load cached data and turn raw nflverse tables into the frames the features need."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz.data.stadiums import HOME_STADIUMS

TERMINAL_DRIVE = {"Touchdown", "Field goal"}


def fix_team(s: pd.Series) -> pd.Series:
    return s.replace(C.TEAM_FIX)


def kickoff_utc(df: pd.DataFrame) -> pd.Series:
    """Kickoff timestamps in UTC. nflverse gives gameday + gametime in US Eastern."""
    local = pd.to_datetime(df["gameday"] + " " + df["gametime"].fillna("13:00"), errors="coerce")
    return local.dt.tz_localize(
        "America/New_York", ambiguous="NaT", nonexistent="NaT"
    ).dt.tz_convert("UTC")


def clean_schedules(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    for c in ("home_team", "away_team"):
        df[c] = fix_team(df[c])
    df["kickoff_utc"] = kickoff_utc(df)
    df["neutral"] = (df["location"] == "Neutral").astype(int)
    df["played"] = df["result"].notna()
    df = df[df["home_team"].isin(HOME_STADIUMS) & df["away_team"].isin(HOME_STADIUMS)]
    df = df.sort_values(["season", "week", "kickoff_utc", "game_id"]).reset_index(drop=True)
    return df


def load_schedules() -> pd.DataFrame:
    return clean_schedules(pd.read_parquet(C.RAW_DIR / "schedules.parquet"))


def aggregate_pbp(pbp: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate play-by-play to (team-game, qb-game) tables.

    team-game: offensive plays/EPA split by pass and rush, success counts and drive outcomes.
    qb-game: passing EPA per passer (used for QB ratings and the starter's identity).
    """
    p = pbp.copy()
    p["posteam"] = fix_team(p["posteam"])
    p["defteam"] = fix_team(p["defteam"])
    p = p[p["posteam"].notna() & p["epa"].notna()]
    p = p[(p["qb_kneel"] != 1) & (p["qb_spike"] != 1) & (p["special"] != 1)]
    p = p[(p["pass"] == 1) | (p["rush"] == 1)]
    p["is_pass"] = (p["pass"] == 1).astype(int)
    p["is_rush"] = 1 - p["is_pass"]
    p["epa_pass"] = p["epa"] * p["is_pass"]
    p["epa_rush"] = p["epa"] * p["is_rush"]
    p["succ"] = p["success"].fillna(0)
    keys = ["game_id", "season", "week", "posteam", "defteam"]
    tg = (
        p.groupby(keys, as_index=False)
        .agg(
            n_pass=("is_pass", "sum"),
            n_rush=("is_rush", "sum"),
            epa_pass=("epa_pass", "sum"),
            epa_rush=("epa_rush", "sum"),
            succ=("succ", "sum"),
        )
        .rename(columns={"posteam": "team", "defteam": "opp"})
    )
    # drive outcomes (one row per fixed drive)
    d = (
        p.dropna(subset=["fixed_drive"])
        .groupby(["game_id", "posteam", "fixed_drive"], as_index=False)["fixed_drive_result"]
        .last()
    )
    d["td"] = (d["fixed_drive_result"] == "Touchdown").astype(int)
    d["fg"] = (d["fixed_drive_result"] == "Field goal").astype(int)
    dr = d.groupby(["game_id", "posteam"], as_index=False).agg(
        drives=("fixed_drive", "size"), td_drives=("td", "sum"), fg_drives=("fg", "sum")
    )
    tg = tg.merge(dr.rename(columns={"posteam": "team"}), on=["game_id", "team"], how="left")

    q = p[(p["is_pass"] == 1) & p["passer_player_id"].notna()]
    qg = q.groupby(
        ["game_id", "season", "week", "posteam", "passer_player_id"], as_index=False
    ).agg(n_db=("is_pass", "sum"), epa_db=("epa", "sum"))
    qg = qg.rename(columns={"posteam": "team", "passer_player_id": "qb_id"})
    return tg, qg


def build_processed() -> None:
    """Aggregate every cached pbp season into two Parquet files."""
    C.PROC_DIR.mkdir(parents=True, exist_ok=True)
    tgs, qgs = [], []
    for path in sorted(C.RAW_DIR.glob("pbp_*.parquet")):
        tg, qg = aggregate_pbp(pd.read_parquet(path))
        tgs.append(tg)
        qgs.append(qg)
    pd.concat(tgs, ignore_index=True).to_parquet(C.PROC_DIR / "team_games.parquet", index=False)
    pd.concat(qgs, ignore_index=True).to_parquet(C.PROC_DIR / "qb_games.parquet", index=False)


def load_team_games() -> tuple[pd.DataFrame, pd.DataFrame]:
    return (
        pd.read_parquet(C.PROC_DIR / "team_games.parquet"),
        pd.read_parquet(C.PROC_DIR / "qb_games.parquet"),
    )


def load_injury_counts() -> pd.DataFrame:
    """Players listed Out/Doubtful per team and report week."""
    path = C.RAW_DIR / "injuries.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["season", "week", "team", "n_out"])
    inj = pd.read_parquet(path)
    inj["team"] = fix_team(inj["team"])
    inj = inj[inj["report_status"].isin(["Out", "Doubtful"])]
    out = (
        inj.groupby(["season", "week", "team"], as_index=False)
        .size()
        .rename(columns={"size": "n_out"})
    )
    return out


__all__ = [
    "aggregate_pbp",
    "build_processed",
    "clean_schedules",
    "load_injury_counts",
    "load_schedules",
    "load_team_games",
    "np",
]
