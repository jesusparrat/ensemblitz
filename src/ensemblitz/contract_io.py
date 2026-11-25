"""Read prediction snapshots as the v1 model, including legacy v0 files.

v0 files under ``predictions/`` are never rewritten. This module only maps them in memory.
Writing new snapshots is ``ledger.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ensemblitz import config as C
from ensemblitz import contract as K

# Simulation size and seed used by predict.py since the first published weeks.
V0_N_SIMS = 20000
V0_SEED = 2026


@dataclass(frozen=True)
class LoadedWeek:
    """A week document normalised to the v1 shape, plus facts about the file itself."""

    path: Path
    version: str
    doc: dict
    headline_kind: str  # week-level: "model_only" if any game is, else "ensemble"
    sha256: str
    headline_kinds: dict  # game_id -> "model_only" | "ensemble"


def load_week(path: Path, odds: dict | None = None) -> LoadedWeek:
    """Read ``path`` (v0 or v1) and return the v1 model. The file is not modified.

    ``odds`` is an optional Odds API report for this week (``reports/odds/*_week*.json``).
    When present, its consensus is attached as an ``odds_api_consensus`` market quote
    (in memory only). Used by tests and by the writer; the site still loads the report
    separately so PR 3 can fix the two-figure display without this PR changing it.
    """
    path = Path(path)
    raw = path.read_bytes()
    doc = json.loads(raw)
    version = K.detect_version(doc)
    if version == K.SCHEMA_VERSION:
        if odds:
            doc = _attach_odds(doc, odds)
        kinds = {g["game_id"]: "model_only" for g in doc["games"]}
        return LoadedWeek(path, version, doc, "model_only", K.sha256_file(path), kinds)
    mapped, kind, kinds = week_from_v0(doc, odds)
    return LoadedWeek(path, "0", mapped, kind, K.sha256_file(path), kinds)


def week_from_v0(doc: dict, odds: dict | None = None) -> tuple[dict, str]:
    """Map a v0 week object to the v1 shape. Returns ``(v1_doc, week_kind, per_game_kinds)``."""
    odds_by_id = {}
    fetched = None
    if odds:
        fetched = odds.get("odds_fetched_at") or odds.get("fetched")
        odds_by_id = {g["game_id"]: {**g, "fetched": fetched} for g in odds.get("games", [])}
    kinds = []
    games = []
    for g in doc["games"]:
        rec, kind = game_from_v0(g, odds_by_id.get(g["game_id"]))
        games.append(rec)
        kinds.append(kind)
    # If any game in the file was saved with the model-only headline, the week is model_only.
    # Pre-web-v2 files have no headline key and are ensemble throughout.
    per = {rec["game_id"]: k for rec, k in zip(games, kinds, strict=True)}
    kind = "model_only" if "model_only" in kinds else "ensemble"
    generated = doc["generated_at"]
    out = {
        "schema_version": K.SCHEMA_VERSION,
        "model_version": doc.get("model_version") or C.MODEL_VERSION,
        "git_sha": "0" * 40,
        "reproducible": False,
        "generated_at_utc": generated,
        "data_cutoff_utc": generated,
        "data_snapshot": {"data/raw/schedules.parquet": "0" * 64},
        "season": int(doc["season"]),
        "week": int(doc["week"]),
        "ensemble_weights": doc.get("ensemble_weights") or {},
        "games": games,
    }
    return out, kind, per


def game_from_v0(g: dict, odds: dict | None = None) -> tuple[dict, str]:
    """Map one v0 game to a v1 game record. Returns ``(record, headline_kind)``."""
    hwp = g["home_win_prob"]
    mo = g.get("model_only")
    legacy = mo is None
    kind = "ensemble" if legacy else g.get("headline") or "model_only"
    if kind != "ensemble" and mo is not None:
        kind = "model_only"

    if mo is not None:
        # The site printed expected points from margin and total; keep that so
        # a slight disagreement between the stored points and margin/total
        # does not change the published figures.
        if mo.get("margin") is not None and mo.get("total") is not None:
            home_pts = (mo["total"] + mo["margin"]) / 2
            away_pts = (mo["total"] - mo["margin"]) / 2
        else:
            home_pts, away_pts = mo["home_points"], mo["away_points"]
        sim = mo["sim"]
        example = {k: mo["example_score"][k] for k in ("home", "away", "prob")}
        home_win = mo["home_win_prob"]
    else:
        margin, total = g["predicted_margin"], g["predicted_total"]
        home_pts = (total + margin) / 2
        away_pts = (total - margin) / 2
        sim = g.get("sim") or {}
        mls = g.get("most_likely_score") or {"home": 0, "away": 0, "prob": 0.0}
        example = {
            "home": int(mls["home"]),
            "away": int(mls["away"]),
            "prob": mls.get("prob") or 0.0,
        }
        home_win = hwp["ensemble"]

    distribution = _distribution_from_v0_sim(sim, home_pts, away_pts)
    market = [_nflverse_quote(g)]
    if odds:
        q = _odds_quote(odds)
        if q is not None:
            market.append(q)

    c = g["context"]
    na = g.get("news_adjustment") or {"applied": False}
    absences = g.get("absences") or {"home": [], "away": []}
    rec = {
        "game_id": g["game_id"],
        "home_team": g["home_team"],
        "away_team": g["away_team"],
        "kickoff_utc": g["kickoff_utc"],
        "generated_at_utc": g.get("generated_at") or g.get("generated_at_utc"),
        "headline": {
            "home_win_prob": home_win,
            "home_points": home_pts,
            "away_points": away_pts,
            "distribution": distribution,
            "example_score": example,
        },
        "ensemble": {
            "home_win_prob": hwp["ensemble"],
            "margin_home": g["predicted_margin"],
            "total": g["predicted_total"],
        },
        "components": {
            k: hwp.get(k) for k in ("elo", "kf", "lgbm", "lgbm_mkt") if hwp.get(k) is not None
        },
        "market": market,
        "context": {
            "home_qb_change": bool(c["home_qb_change"]),
            "away_qb_change": bool(c["away_qb_change"]),
            "home_rest_days": int(c.get("home_rest_days", c.get("home_rest", 0))),
            "away_rest_days": int(c.get("away_rest_days", c.get("away_rest", 0))),
            "dome": bool(c["dome"]),
            "weather_known": bool(
                c["weather_known"] if "weather_known" in c else c.get("temp") is not None
            ),
            "temp_f": c.get("temp_f", c.get("temp")),
            "wind_mph": c.get("wind_mph", c.get("wind")),
            "home_out_lag": int(c["home_out_lag"]),
            "away_out_lag": int(c["away_out_lag"]),
        },
        "absences": {
            "home": [a for a in absences.get("home", [])],
            "away": [a for a in absences.get("away", [])],
        },
        "news_adjustment": _news_from_v0(na),
    }
    return rec, kind


def _distribution_from_v0_sim(sim: dict, home_pts: float, away_pts: float) -> dict:
    """Build a v1 distribution from a v0 ``sim`` block (model_only or ensemble)."""
    if "home_q10" in sim:
        home_r = [sim["home_q10"], sim["home_q90"]]
        away_r = [sim["away_q10"], sim["away_q90"]]
    else:
        # Pre-web-v2 files only stored margin and total ranges. Approximate the team
        # ranges from those; they are not shown as the current published week (those
        # files have model_only.sim with team ranges).
        t0, t1 = sim.get("total_q10"), sim.get("total_q90")
        m0, m1 = sim.get("margin_q10"), sim.get("margin_q90")
        if t0 is not None and m0 is not None:
            home_r = [(t0 + m0) / 2, (t1 + m1) / 2]
            away_r = [(t0 - m1) / 2, (t1 - m0) / 2]
        else:
            home_r = [home_pts, home_pts]
            away_r = [away_pts, away_pts]
    return {
        "n_sims": V0_N_SIMS,
        "seed": V0_SEED,
        "p_home": sim.get("p_home"),
        "home_points": home_r,
        "away_points": away_r,
        "margin_home": [sim.get("margin_q10"), sim.get("margin_q90")],
        "total": [sim.get("total_q10"), sim.get("total_q90")],
    }


def _nflverse_quote(g: dict) -> dict:
    m = g["market"]
    hwp = g["home_win_prob"]
    return {
        "source": "nflverse_line",
        "captured_at_utc": g.get("generated_at") or g.get("generated_at_utc"),
        "is_closing": False,
        "home_win_prob": hwp.get("market"),
        "margin_home": m.get("spread_line"),
        "total_line": m.get("total_line"),
        "home_moneyline": m.get("home_moneyline"),
        "away_moneyline": m.get("away_moneyline"),
    }


def _odds_quote(odds: dict) -> dict | None:
    if odds.get("consensus_home_prob_shin") is None:
        return None
    captured = odds.get("fetched") or odds.get("captured_at_utc") or odds.get("odds_fetched_at")
    q: dict[str, Any] = {
        "source": "odds_api_consensus",
        "captured_at_utc": captured,
        "is_closing": False,
        "home_win_prob": odds["consensus_home_prob_shin"],
        "margin_home": K.odds_api_margin_home(odds.get("book_spread_home")),
        "total_line": odds.get("book_total"),
        "n_books": odds.get("n_books"),
    }
    return q


def _news_from_v0(na: dict) -> dict:
    out = {
        "applied": bool(na.get("applied")),
        "applies_to": na.get("applies_to") or "ensemble",
    }
    if "margin_points" in na:
        out["margin_points"] = na["margin_points"]
    if "home_points_lost" in na:
        out["home_points_lost"] = na["home_points_lost"]
    if "away_points_lost" in na:
        out["away_points_lost"] = na["away_points_lost"]
    if "prob_home_before" in na or "home_win_prob_before" in na:
        out["home_win_prob_before"] = na.get("home_win_prob_before", na.get("prob_home_before"))
    if "margin_before" in na or "margin_home_before" in na:
        out["margin_home_before"] = na.get("margin_home_before", na.get("margin_before"))
    if "items" in na:
        out["items"] = na["items"]
    return out


def _attach_odds(doc: dict, odds: dict) -> dict:
    """Return a copy of a v1 doc with the Odds API consensus added when missing."""
    import copy

    out = copy.deepcopy(doc)
    fetched = odds.get("odds_fetched_at") or odds.get("fetched")
    by_id = {g["game_id"]: {**g, "fetched": fetched} for g in odds.get("games", [])}
    for g in out["games"]:
        if any(q.get("source") == "odds_api_consensus" for q in g["market"]):
            continue
        src = by_id.get(g["game_id"])
        if not src:
            continue
        q = _odds_quote(src)
        if q is not None:
            g["market"].append(q)
    return out


def market_quote(game: dict, source: str) -> dict | None:
    for q in game.get("market") or []:
        if q.get("source") == source:
            return q
    return None


__all__ = [
    "LoadedWeek",
    "V0_N_SIMS",
    "V0_SEED",
    "game_from_v0",
    "latest_pick_before_kickoff",
    "load_week",
    "market_quote",
    "week_from_v0",
]


def latest_pick_before_kickoff(
    game_id: str, root: Path | None = None
) -> tuple[LoadedWeek, dict, str] | None:
    """The latest snapshot whose *publication* time is strictly before this game's kickoff.

    Publication time is the first git commit of those bytes, or the document's
    ``generated_at_utc`` when the file is not yet in git. The file's own timestamp
    is never the authority for a committed artifact (it can be rewritten).
    """
    from ensemblitz import ledger as L

    root = (root or C.ROOT).resolve()
    candidates: list[tuple[str, LoadedWeek, dict]] = []
    for art in L.iter_artifacts(root):
        loaded = load_week(art.path)
        game = next((g for g in loaded.doc["games"] if g["game_id"] == game_id), None)
        if game is None:
            continue
        published = L.publication_time_utc(art, root)
        if published < game["kickoff_utc"]:
            candidates.append((published, loaded, game))
    if not candidates:
        return None
    published, loaded, game = max(candidates, key=lambda t: (t[0], t[1].path.as_posix()))
    return loaded, game, published
