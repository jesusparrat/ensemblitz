"""Optional news file and the conservative, per-player strength adjustment built on it.

File: ``news/<season>/weekXX.json``, a JSON list of items (see README, "Noticias"). It moves
*predictions only*, never the backtest (there is no historical news archive to validate against).

For each item the team loses ``value x status_weight x freshness`` points of margin, where
``value`` is the player's points-per-game over a replacement from ``ensemblitz.players``
(``out`` = 1, ``doubtful`` = 0.75, ``questionable`` = 0.25, ``returning``/``other`` = 0).
``freshness`` guards against double counting: closing lines already move when news is public, so
items posted up to 12 h before the prediction count fully, up to 48 h count half, older ones 0.25.
A player missing from the table (rookie, name mismatch) falls back to half of the position prior.
A team's total is capped at ``TEAM_CAP``. The margin change shifts the win probability on a normal
scale with the market margin sd (13.5).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr, ndtri

from ensemblitz import config as C
from ensemblitz import players as PL
from ensemblitz.models.market import MARGIN_SD

log = logging.getLogger(__name__)

STATUSES = ("out", "doubtful", "questionable", "returning", "other")
STATUS_WEIGHT = {"out": 1.0, "doubtful": 0.75, "questionable": 0.25, "returning": 0.0, "other": 0.0}
TEAM_CAP = 7.0
FALLBACK_PTS = {
    "QB": 2.0,
    "EDGE": 0.65,
    "OL": 0.45,
    "WR": 0.4,
    "CB": 0.45,
    "DT": 0.35,
    "RB": 0.25,
    "LB": 0.3,
    "TE": 0.25,
    "S": 0.3,
}
REQUIRED = ("team", "player", "status")


def news_path(season: int, week: int, root: Path | None = None) -> Path:
    return (root or C.ROOT) / "news" / str(season) / f"week{week:02d}.json"


def load_news(path: Path) -> list[dict]:
    """Read and normalise a news file. Invalid items are skipped with a warning; no file -> []."""
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    items = []
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict) or any(not it.get(k) for k in REQUIRED):
            log.warning("news item skipped (missing fields): %s", it)
            continue
        status = str(it["status"]).lower()
        items.append(
            {
                "team": str(it["team"]).upper(),
                "player": it["player"],
                "position": str(it.get("position") or "").upper(),
                "status": status if status in STATUSES else "other",
                "summary_es": it.get("summary_es", ""),
                "source_handle": it.get("source_handle"),
                "source_url": it.get("source_url"),
                "posted_at": it.get("posted_at"),
                "impact_note_es": it.get("impact_note_es"),
                "starter": bool(it.get("starter", True)),
            }
        )
    return sorted(items, key=lambda x: x["posted_at"] or "", reverse=True)


def freshness(posted_at: str | None, as_of: str | None) -> float:
    """1.0 if posted within 12 h of ``as_of``, 0.5 within 48 h, else 0.25 (market has caught up)."""
    if not posted_at or not as_of:
        return 1.0
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    age = datetime.strptime(as_of, fmt) - datetime.strptime(posted_at, fmt)
    if age < timedelta(0):
        return 0.0  # posted after the prediction: not known yet
    return 1.0 if age <= timedelta(hours=12) else 0.5 if age <= timedelta(hours=48) else 0.25


def item_points(it: dict, values: pd.DataFrame | None, as_of: str | None) -> dict | None:
    """Margin points an item takes from its team, with the audit trail."""
    w = STATUS_WEIGHT[it["status"]]
    if w == 0 or not it["starter"]:
        return None
    fresh = freshness(it["posted_at"], as_of)
    if fresh == 0:
        return None
    row = PL.lookup(values, it["player"], it["position"]) if values is not None else None
    if row is not None:
        value, source = float(row["value_pts"]), f"player value ({row['method']})"
    else:
        grp = PL.GROUPS.get(it["position"], "")
        value, source = FALLBACK_PTS.get(grp, 0.0), "position prior (player not in table)"
    pts = value * w * fresh
    if pts <= 0:
        return None
    return {
        "team": it["team"],
        "player": it["player"],
        "position": it["position"],
        "status": it["status"],
        "value_pts": round(value, 2),
        "status_weight": w,
        "freshness": fresh,
        "points": round(pts, 2),
        "source": source,
    }


def team_points(
    items: list[dict], team: str, values: pd.DataFrame | None, as_of: str | None = None
) -> tuple[float, list[dict]]:
    seen: set[str] = set()
    hits = []
    for it in items:
        if it["team"] != team or it["player"] in seen:
            continue
        h = item_points(it, values, as_of)
        if h:
            seen.add(it["player"])
            hits.append(h)
    return min(sum(h["points"] for h in hits), TEAM_CAP), hits


def adjust_game(
    prob_home: float,
    margin: float,
    home: str,
    away: str,
    items: list[dict],
    values: pd.DataFrame | None,
    as_of: str | None = None,
) -> dict:
    """Return the adjusted probability/margin and an audit record for one game."""
    ph, hh = team_points(items, home, values, as_of)
    pa, ha = team_points(items, away, values, as_of)
    delta = -ph + pa
    after = float(ndtr(ndtri(np.clip(prob_home, 1e-4, 1 - 1e-4)) + delta / MARGIN_SD))
    return {
        "applied": bool(hh or ha),
        "margin_points": round(delta, 2),
        "home_points_lost": round(ph, 2),
        "away_points_lost": round(pa, 2),
        "prob_home_before": round(float(prob_home), 4),
        "prob_home_after": round(after, 4),
        "margin_before": round(float(margin), 2),
        "margin_after": round(float(margin + delta), 2),
        "items": hh + ha,
    }


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
