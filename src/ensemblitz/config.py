"""Paths and global constants."""

from __future__ import annotations

import os
from pathlib import Path

from ensemblitz import __version__

MODEL_VERSION = __version__

ROOT = Path(os.environ.get("ENSEMBLITZ_ROOT", Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROC_DIR = DATA_DIR / "processed"
PRED_DIR = ROOT / "predictions"
RESULTS_DIR = ROOT / "results"
REPORTS_DIR = ROOT / "reports"

FIRST_SEASON = 2015
FIRST_BACKTEST_SEASON = 2018
LAST_BACKTEST_SEASON = 2025
# Out-of-sample predictions start one step earlier so the stacker has a pool to learn from.
WARMUP_SEASON = 2016

# nflverse still carries old franchise codes in some seasons.
TEAM_FIX = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "WSH": "WAS", "JAC": "JAX"}
