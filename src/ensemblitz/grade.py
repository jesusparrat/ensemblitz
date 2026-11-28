"""Grade frozen predictions. Only picks generated before kickoff count."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz import contract as K
from ensemblitz import contract_io
from ensemblitz import ledger as L
from ensemblitz import outcome_bands as OB
from ensemblitz.data import load

COMPONENTS = ["market", "elo", "kf", "lgbm", "lgbm_mkt", "ensemble", "ensemble_model_only"]
# Records written before the model-only headline (web v2) published the blended ensemble pick.
LEGACY_HEADLINE = "ensemble"
HEADLINE_COMPONENT = {"model_only": "ensemble_model_only", "ensemble": "ensemble"}


def _view(g: dict, published_at: str | None = None, headline_kind: str | None = None) -> dict:
    """v0 or v1 game → the flat fields the grader already uses.

    ``published_at``, when given, is the ledger/git publication time and is the
    authority for the before-kickoff check. The file's own ``generated_at`` is
    only used when that time is not available (unit tests, a snapshot not yet
    committed).
    """
    if "headline" in g and isinstance(g["headline"], dict):
        h = g["headline"]
        kind = headline_kind or "model_only"
        pm = K.margin_home(h) if kind == "model_only" else g["ensemble"]["margin_home"]
        pt = K.total(h) if kind == "model_only" else g["ensemble"]["total"]
        pick = (
            K.pick(g)
            if kind == "model_only"
            else (g["home_team"] if g["ensemble"]["home_win_prob"] >= 0.5 else g["away_team"])
        )
        nfl = next((q for q in g["market"] if q.get("source") == "nflverse_line"), {})
        hwp = {
            "market": nfl.get("home_win_prob"),
            "elo": g["components"].get("elo"),
            "kf": g["components"].get("kf"),
            "lgbm": g["components"].get("lgbm"),
            "lgbm_mkt": g["components"].get("lgbm_mkt"),
            "ensemble": g["ensemble"]["home_win_prob"],
            "ensemble_model_only": h["home_win_prob"],
        }
        season, week = (None, None)
        parts = g["game_id"].split("_")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            season, week = int(parts[0]), int(parts[1])
        return {
            "game_id": g["game_id"],
            "season": g.get("season", season),
            "week": g.get("week", week),
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "kickoff_utc": g["kickoff_utc"],
            "generated_at": published_at or g.get("generated_at_utc") or g.get("generated_at"),
            "headline": kind,
            "pick": pick,
            "predicted_margin": pm,
            "predicted_total": pt,
            "market": {"spread_line": nfl.get("margin_home")},
            "home_win_prob": hwp,
            "model_only": {
                "margin": K.margin_home(h),
                "total": K.total(h),
                "home_win_prob": h["home_win_prob"],
            },
        }
    out = dict(g)
    if published_at is not None:
        out["generated_at"] = published_at
    return out


def grade_games(
    preds: list[dict],
    schedule: pd.DataFrame,
    published_at: list[str | None] | None = None,
    headline_kind: list[str | None] | None = None,
) -> list[dict]:
    """Return graded rows for finished games whose pick was made before kickoff."""
    res = schedule.set_index("game_id")
    out = []
    for i, raw in enumerate(preds):
        pub = None if published_at is None else published_at[i]
        kind = None if headline_kind is None else headline_kind[i]
        g = _view(raw, pub, kind)
        if g["game_id"] not in res.index:
            continue
        s = res.loc[g["game_id"]]
        if pd.isna(s["result"]) or L.parse_utc(g["generated_at"]) >= L.parse_utc(g["kickoff_utc"]):
            continue
        margin = float(s["result"])
        headline = g.get("headline", LEGACY_HEADLINE)
        if isinstance(headline, dict):
            headline = "model_only"
        mo = g.get("model_only")
        pm = mo["margin"] if mo else g["predicted_margin"]
        row = {
            "game_id": g["game_id"],
            "season": g["season"],
            "week": g["week"],
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "result": margin,
            "total": float(s["total"]),
            "headline": headline,
            "pick": g["pick"],
            "predicted_margin": pm,
            "predicted_total": mo["total"] if mo else g["predicted_total"],
            "spread_line": g["market"]["spread_line"],
        }
        if margin != 0:
            y = float(margin > 0)
            for c in COMPONENTS:
                p = g["home_win_prob"].get(c)
                if p is None:
                    continue
                p = float(np.clip(p, 1e-4, 1 - 1e-4))
                row[f"{c}_correct"] = int((p > 0.5) == (y == 1))
                row[f"{c}_logloss"] = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)))
            # the graded headline: whichever number was published as the pick
            hc = HEADLINE_COMPONENT.get(headline, "ensemble")
            row["headline_correct"] = row.get(f"{hc}_correct")
        sp = g["market"]["spread_line"]
        if sp is not None and pm is not None and pm != sp and margin != sp:
            row["ats_win"] = int(((margin - sp) > 0) == (pm > sp))
        bands = raw.get("outcome_bands") if isinstance(raw, dict) else None
        if isinstance(bands, dict) and bands.get("top3"):
            stored = [b["id"] for b in bands.get("bands") or []]
            if OB.spec_for_ids(stored) is not None:
                bid = OB.band_for_margin(int(round(margin)), stored)
                row["outcome_band"] = bid
                row["outcome_band_rank"] = OB.rank_of(bid, list(bands["top3"]))
        out.append(row)
    return out


def select_pre_kickoff_picks(
    root: Path | None = None,
) -> dict[str, tuple[dict, str, str, str, int, int]]:
    """Select each game's latest snapshot published strictly before ``g['kickoff_utc']``.

    Tie-breaking uses ``(published_dt, art.rel)``. Headline kind is taken per game from
    ``loaded.headline_kinds[game_id]``. Games with no snapshot published strictly before
    kickoff are omitted (ungradable) and never fall back to a post-kickoff snapshot.

    Returns ``{game_id: (game, published_utc, art_rel, headline_kind, season, week)}``.
    """
    root = (root or C.ROOT).resolve()
    by_id: dict[str, tuple[dict, str, str, str, int, int]] = {}
    for art in L.iter_artifacts(root):
        loaded = contract_io.load_week(art.path)
        published = L.publication_time_utc(art, root)
        pub_dt = L.parse_utc(published)
        for g in loaded.doc["games"]:
            if pub_dt >= L.parse_utc(g["kickoff_utc"]):
                continue
            gid = g["game_id"]
            kind = loaded.headline_kinds.get(gid, loaded.headline_kind)
            prev = by_id.get(gid)
            if prev is None or (pub_dt, art.rel) > (L.parse_utc(prev[1]), prev[2]):
                by_id[gid] = (
                    g,
                    published,
                    art.rel,
                    kind,
                    loaded.doc["season"],
                    loaded.doc["week"],
                )
    return by_id


def run_grade(root: Path | None = None, schedule: pd.DataFrame | None = None) -> dict:
    """Grade the latest snapshot of each game that was published strictly before kickoff."""
    resolved_root = (root or C.ROOT).resolve()
    results_dir = (resolved_root / "results") if root is not None else C.RESULTS_DIR
    sched = schedule if schedule is not None else load.load_schedules()
    by_id = select_pre_kickoff_picks(resolved_root)
    # Attach season/week for the grader and group by week for the results files.
    buckets: dict[tuple[int, int], list[tuple[dict, str, str]]] = {}
    for _gid, (g, published, _rel, kind, season, week) in by_id.items():
        g = {**g, "season": season, "week": week}
        buckets.setdefault((season, week), []).append((g, published, kind))
    graded: list[dict] = []
    for (season, week), items in sorted(buckets.items()):
        games = [g for g, _, _ in items]
        pubs = [p for _, p, _ in items]
        kinds = [k for _, _, k in items]
        rows = grade_games(games, sched, published_at=pubs, headline_kind=kinds)
        if rows:
            d = results_dir / str(season)
            d.mkdir(parents=True, exist_ok=True)
            (d / f"week{week:02d}.json").write_text(json.dumps(rows, indent=1))
            graded += rows
    summary = summarize(graded)
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    (results_dir / "summary.md").write_text(summary_md(summary))
    return summary


def summarize(rows: list[dict]) -> dict:
    df = pd.DataFrame(rows)
    out: dict = {"n_graded": len(df), "models": {}}
    if df.empty:
        return out
    for c in COMPONENTS:
        if f"{c}_correct" in df:
            d = df.dropna(subset=[f"{c}_correct"])
            out["models"][c] = {
                "n": len(d),
                "accuracy": float(d[f"{c}_correct"].mean()),
                "log_loss": float(d[f"{c}_logloss"].mean()),
            }
    if "ats_win" in df:
        d = df.dropna(subset=["ats_win"])
        out["ats"] = {"w": int(d["ats_win"].sum()), "l": int(len(d) - d["ats_win"].sum())}
    if "headline_correct" in df:
        d = df.dropna(subset=["headline_correct"])
        out["headline"] = {
            h: {"n": len(x), "accuracy": float(x["headline_correct"].mean())}
            for h, x in d.groupby("headline")
        }
    if "outcome_band_rank" in df:
        d = df.dropna(subset=["outcome_band_rank"])
        n = len(d)
        if n:
            ranks = d["outcome_band_rank"].map(lambda x: int(x) if str(x).isdigit() else 0)
            n1 = int((ranks == 1).sum())
            n2 = int((ranks == 2).sum())
            n3 = int((ranks == 3).sum())
            outside = n - n1 - n2 - n3
            out["outcome_bands"] = {
                "n": n,
                "rank_1": n1,
                "rank_2": n2,
                "rank_3": n3,
                "outside": outside,
                "top1": n1 / n,
                "top2": (n1 + n2) / n,
                "top3": (n1 + n2 + n3) / n,
            }
    out["weeks"] = sorted({f"{r['season']}-W{r['week']:02d}" for r in rows})
    return out


LABELS = {
    "ensemble_model_only": "model only (headline)",
    "ensemble": "model blended with the market",
    "market": "market",
}


def summary_md(s: dict) -> str:
    lines = [
        "# Results of the frozen picks",
        "",
        f"Graded games (pick saved before kickoff): {s['n_graded']}",
        "",
        "Since web v2 the headline pick is the model on its own (`ensemble_model_only`). "
        "Earlier picks were the blended ensemble; each graded row records which one it was.",
        "",
    ]
    if s["models"]:
        lines += ["| Source | N | Acierto | Log loss |", "|---|---|---|---|"]
        for c, r in s["models"].items():
            lines.append(
                f"| {LABELS.get(c, c)} | {r['n']} | {r['accuracy'] * 100:.1f}% | {r['log_loss']:.3f} |"
            )
    if "ats" in s:
        lines += ["", f"Against the spread (headline margin): {s['ats']['w']}-{s['ats']['l']}"]
    ob = s.get("outcome_bands")
    if ob:
        lines += [
            "",
            "## Outcome bands",
            "",
            f"Graded games that stored a top 3: {ob['n']}. "
            "Top 2 and top 3 are cumulative (the result landed in the first two, or in the three).",
            "",
            "| Where the result landed | N | Share |",
            "|---|---|---|",
            f"| Top 1 | {ob['rank_1']} | {ob['top1'] * 100:.1f}% |",
            f"| Top 2 | {ob['rank_1'] + ob['rank_2']} | {ob['top2'] * 100:.1f}% |",
            f"| Top 3 | {ob['rank_1'] + ob['rank_2'] + ob['rank_3']} | {ob['top3'] * 100:.1f}% |",
            f"| Outside the top 3 | {ob['outside']} | {(ob['outside'] / ob['n']) * 100:.1f}% |",
        ]
    return "\n".join(lines) + "\n"


__all__ = ["grade_games", "run_grade", "select_pre_kickoff_picks"]
