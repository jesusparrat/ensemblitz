"""Download nflverse data (via nflreadpy) and cache it as Parquet under ``data/``."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date

import pandas as pd

from ensemblitz import config as C

log = logging.getLogger(__name__)

PBP_COLS = [
    "game_id",
    "season",
    "week",
    "season_type",
    "posteam",
    "defteam",
    "epa",
    "success",
    "pass",
    "rush",
    "qb_dropback",
    "qb_kneel",
    "qb_spike",
    "special",
    "play_type",
    "passer_player_id",
    "drive",
    "fixed_drive",
    "fixed_drive_result",
    "sack",
]


def current_season(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 3 else today.year - 1


def _ensure_dirs() -> None:
    C.RAW_DIR.mkdir(parents=True, exist_ok=True)
    C.PROC_DIR.mkdir(parents=True, exist_ok=True)


def update_schedules(seasons: Iterable[int]) -> pd.DataFrame:
    import nflreadpy as nfl

    _ensure_dirs()
    df = nfl.load_schedules(list(seasons)).to_pandas()
    df.to_parquet(C.RAW_DIR / "schedules.parquet", index=False)
    return df


def update_pbp(seasons: Iterable[int], refresh_from: int | None = None) -> None:
    """Cache slim play-by-play per season. Past seasons are only downloaded once."""
    import nflreadpy as nfl

    _ensure_dirs()
    for s in seasons:
        path = C.RAW_DIR / f"pbp_{s}.parquet"
        if path.exists() and (refresh_from is None or s < refresh_from):
            continue
        log.info("downloading pbp %s", s)
        try:
            pbp = nfl.load_pbp([s]).to_pandas()
        except Exception as exc:  # season not published yet
            log.warning("pbp %s unavailable: %s", s, exc)
            continue
        cols = [c for c in PBP_COLS if c in pbp.columns]
        pbp[cols].to_parquet(path, index=False)


def update_injuries(seasons: Iterable[int]) -> None:
    import nflreadpy as nfl

    _ensure_dirs()
    frames = []
    for s in seasons:
        try:
            frames.append(nfl.load_injuries([s]).to_pandas())
        except Exception as exc:
            log.warning("injuries %s unavailable: %s", s, exc)
    if frames:
        cols = ["season", "week", "team", "gsis_id", "position", "report_status"]
        inj = pd.concat(frames, ignore_index=True)
        inj[[c for c in cols if c in inj.columns]].to_parquet(
            C.RAW_DIR / "injuries.parquet", index=False
        )


def update_all(first: int = C.FIRST_SEASON, last: int | None = None) -> None:
    """Refresh schedules, injuries and the current season's pbp; fetch missing past seasons."""
    last = last or current_season()
    seasons = list(range(first, last + 1))
    update_schedules(seasons)
    update_pbp(seasons, refresh_from=last)
    update_injuries(seasons)
