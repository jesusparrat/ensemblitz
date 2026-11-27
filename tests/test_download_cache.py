"""Validation of cached closed-season play-by-play parquets in download.py."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd

from ensemblitz import config as C
from ensemblitz.data import download


def _valid_pbp_df(season: int) -> pd.DataFrame:
    row = {col: 1 for col in download.PBP_COLS}
    row["game_id"] = f"{season}_01_AAA_BBB"
    row["season"] = season
    row["season_type"] = "REG"
    row["posteam"] = "BBB"
    row["defteam"] = "AAA"
    row["play_type"] = "pass"
    row["passer_player_id"] = "00-0000001"
    row["fixed_drive_result"] = "Touchdown"
    return pd.DataFrame([row])


def test_pbp_schema_hash_is_stable_and_sensitive(monkeypatch) -> None:
    h1 = download.pbp_schema_hash()
    assert len(h1) == 16
    assert h1 == download.pbp_schema_hash()
    monkeypatch.setattr(download, "PBP_COLS", [*download.PBP_COLS, "extra_col"])
    assert download.pbp_schema_hash() != h1


def test_is_valid_pbp_cache_checks_readability_rows_columns_and_season(tmp_path: Path) -> None:
    missing = tmp_path / "pbp_2024.parquet"
    assert download.is_valid_pbp_cache(missing, expected_season=2024) is False

    # Empty file
    missing.write_bytes(b"")
    assert download.is_valid_pbp_cache(missing, expected_season=2024) is False

    # Corrupt bytes
    missing.write_bytes(b"not a parquet file")
    assert download.is_valid_pbp_cache(missing, expected_season=2024) is False

    # Empty DataFrame with valid schema
    _valid_pbp_df(2024).iloc[0:0].to_parquet(missing, index=False)
    assert download.is_valid_pbp_cache(missing, expected_season=2024) is False

    # Missing required PBP_COLS column
    _valid_pbp_df(2024).drop(columns=["sack"]).to_parquet(missing, index=False)
    assert download.is_valid_pbp_cache(missing, expected_season=2024) is False

    # Wrong season inside file
    _valid_pbp_df(2023).to_parquet(missing, index=False)
    assert download.is_valid_pbp_cache(missing, expected_season=2024) is False

    # Valid parquet passes
    _valid_pbp_df(2024).to_parquet(missing, index=False)
    assert download.is_valid_pbp_cache(missing, expected_season=2024) is True


def test_update_pbp_validates_cache_and_always_refreshes_current_season(
    tmp_path: Path, monkeypatch
) -> None:
    raw_dir = tmp_path / "raw"
    proc_dir = tmp_path / "processed"
    raw_dir.mkdir(parents=True)
    monkeypatch.setattr(C, "RAW_DIR", raw_dir)
    monkeypatch.setattr(C, "PROC_DIR", proc_dir)

    # 2023: corrupt cache -> must re-download
    (raw_dir / "pbp_2023.parquet").write_bytes(b"corrupt")
    # 2024: valid closed-season cache -> must reuse without downloading
    _valid_pbp_df(2024).to_parquet(raw_dir / "pbp_2024.parquet", index=False)
    # 2026: valid current-season file -> must STILL re-download (refresh_from=2026)
    _valid_pbp_df(2026).to_parquet(raw_dir / "pbp_2026.parquet", index=False)

    downloaded: list[int] = []

    class _FakeTable:
        def __init__(self, df: pd.DataFrame) -> None:
            self._df = df

        def to_pandas(self) -> pd.DataFrame:
            return self._df

    fake_nfl = types.ModuleType("nflreadpy")

    def _load_pbp(seasons: list[int]) -> _FakeTable:
        s = seasons[0]
        downloaded.append(s)
        return _FakeTable(_valid_pbp_df(s))

    fake_nfl.load_pbp = _load_pbp  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "nflreadpy", fake_nfl)

    download.update_pbp([2023, 2024, 2026], refresh_from=2026)

    assert downloaded == [2023, 2026]
    assert download.is_valid_pbp_cache(raw_dir / "pbp_2023.parquet", expected_season=2023) is True
    assert download.is_valid_pbp_cache(raw_dir / "pbp_2024.parquet", expected_season=2024) is True
    assert download.is_valid_pbp_cache(raw_dir / "pbp_2026.parquet", expected_season=2026) is True
