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
        # practice_status and date_modified are kept for Phase 1 (see reports/BASELINE.md).
        cols = [
            "season",
            "week",
            "team",
            "gsis_id",
            "position",
            "report_status",
            "practice_status",
            "date_modified",
        ]
        inj = pd.concat(frames, ignore_index=True)
        inj[[c for c in cols if c in inj.columns]].to_parquet(
            C.RAW_DIR / "injuries.parquet", index=False
        )


def update_players(seasons: Iterable[int]) -> None:
    """Weekly player stats, snap counts and the id map (gsis <-> pfr) used by the injury impact."""
    import nflreadpy as nfl

    _ensure_dirs()
    seasons = list(seasons)
    ps = nfl.load_player_stats(seasons).to_pandas()
    keep = [
        "player_id", "player_display_name", "position", "season", "week", "season_type", "team",
        "attempts", "sacks_suffered", "passing_epa", "carries", "rushing_epa", "targets",
        "receiving_epa", "def_sacks", "def_qb_hits", "def_tackles_for_loss",
        "def_fumbles_forced", "def_interceptions", "def_pass_defended", "def_tackles_solo",
        "def_tackle_assists",
    ]  # fmt: skip
    ps[[c for c in keep if c in ps.columns]].to_parquet(
        C.RAW_DIR / "player_stats.parquet", index=False
    )
    sn = nfl.load_snap_counts(seasons).to_pandas()
    sn[
        ["season", "week", "game_type", "pfr_player_id", "position", "team", "offense_pct",
         "defense_pct", "offense_snaps", "defense_snaps", "st_snaps"]
    ].to_parquet(C.RAW_DIR / "snap_counts.parquet", index=False)  # fmt: skip
    nfl.load_players().to_pandas()[["gsis_id", "pfr_id"]].dropna().to_parquet(
        C.RAW_DIR / "player_ids.parquet", index=False
    )


def update_history(first: int = 1999, last: int = C.FIRST_SEASON - 1) -> None:
    """Old schedules (results and closing spreads) used only to estimate the margin distribution."""
    import nflreadpy as nfl

    _ensure_dirs()
    h = nfl.load_schedules(list(range(first, last + 1))).to_pandas()
    h = h[["game_id", "season", "week", "game_type", "result", "spread_line"]]
    h.to_parquet(C.RAW_DIR / "schedules_history.parquet", index=False)


def update_all(first: int = C.FIRST_SEASON, last: int | None = None) -> None:
    """Refresh schedules, injuries and the current season's pbp; fetch missing past seasons."""
    last = last or current_season()
    seasons = list(range(first, last + 1))
    update_schedules(seasons)
    update_pbp(seasons, refresh_from=last)
    update_injuries(seasons)
    update_history()
    update_players([s for s in seasons if s >= C.FIRST_SEASON])
