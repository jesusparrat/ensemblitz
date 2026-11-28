"""Predict upcoming games and freeze the picks as JSON."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ensemblitz import config as C
from ensemblitz import contract as K
from ensemblitz import explain as X
from ensemblitz import ledger as L
from ensemblitz import news as N
from ensemblitz import outcome_bands as OB
from ensemblitz import pipeline as P
from ensemblitz.features.build import feature_columns
from ensemblitz.models import gbm
from ensemblitz.models.ensemble import Ensemble
from ensemblitz.models.market import implied_spread, margin_to_prob
from ensemblitz.sim import SimParams, likely_score, simulate_games, summarize_sim

log = logging.getLogger(__name__)


def pred_path(season: int, week: int) -> Path:
    return C.PRED_DIR / str(season) / f"week{week:02d}.json"


def next_weeks(feats: pd.DataFrame, season: int, n: int = 1) -> list[int]:
    s = feats[(feats["season"] == season) & ~feats["played"]]
    return [int(w) for w in sorted(s["week"].unique())[:n]]


def _week_kickoffs(feats: pd.DataFrame, season: int, week: int) -> list[dict]:
    sub = feats[(feats["season"] == season) & (feats["week"] == week)]
    if "kickoff_utc" not in sub.columns:
        return []
    out: list[dict] = []
    for k in sub["kickoff_utc"]:
        if pd.isna(k):
            continue
        stamp = k.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(k, "strftime") else str(k)
        out.append({"kickoff_utc": stamp})
    return out


def open_next_weeks(
    feats: pd.DataFrame,
    season: int,
    n: int = 1,
    *,
    now: datetime | None = None,
    root: Path | None = None,
) -> list[int]:
    """Next unplayed weeks that still have at least one game with ``kickoff_utc > now``.

    A week remains open for mid-week updates (for example Friday after Thursday Night
    Football) while any game has ``kickoff_utc > now``; games at or past kickoff are
    frozen to their latest pre-kickoff canonical record. Once all games in a week have
    passed kickoff (for example Tuesday morning before Monday Night Football scores land
    in nflverse), the week is locked and skipped here. Explicit ``--week`` calls still
    target the requested week and raise ``WeekLockedError`` if all games have started.
    """
    now_dt = now or datetime.now(UTC)
    s = feats[(feats["season"] == season) & ~feats["played"]]
    open_wks: list[int] = []
    for w in sorted(s["week"].unique()):
        wi = int(w)
        if L.week_is_locked(
            season, wi, now=now_dt, root=root, games=_week_kickoffs(feats, season, wi)
        ):
            continue
        open_wks.append(wi)
        if len(open_wks) >= n:
            break
    return open_wks


def has_open_games(
    season: int | None = None,
    *,
    now: datetime | None = None,
    root: Path | None = None,
    schedules: pd.DataFrame | None = None,
) -> bool:
    """Return True if at least one unplayed game in ``season`` has ``kickoff_utc > now``.

    Reads only the schedules table so automated workflows can skip Odds API calls cleanly
    when no open games remain, without fitting the full model pipeline.
    """
    from ensemblitz.data import download, load

    season = season or download.current_season()
    sched = schedules if schedules is not None else load.load_schedules()
    return bool(open_next_weeks(sched, season, n=1, now=now, root=root))


def fill_missing_spread(feats: pd.DataFrame) -> pd.DataFrame:
    """Unplayed games with moneylines but no spread get the spread those moneylines imply.

    nflverse sometimes publishes the moneylines and total of an upcoming game before (or without)
    the spread. Without a spread the stack silently fell back to the no-market model, so the pick
    could sit 16 points away from a market that was right there in the same row (2026 week 12,
    NYJ at MIA). The market components only need a margin, and the moneyline gives one.
    """
    missing = (~feats["played"]) & feats["spread_line"].isna()
    implied = implied_spread(feats["home_moneyline"], feats["away_moneyline"])
    fill = missing & pd.Series(implied, index=feats.index).notna()
    if fill.any():
        feats = feats.copy()
        feats.loc[fill, "spread_line"] = np.round(implied[fill.to_numpy()] * 2) / 2
        log.info("spread implied from moneylines for %d game(s)", int(fill.sum()))
    return feats


def build_frame(season: int) -> pd.DataFrame:
    """Features + every component for all games up to ``season`` (future games included)."""
    feats = P.make_features()
    feats = feats[feats["season"] <= season]
    feats = fill_missing_spread(feats)
    feats, _ = P.add_kf(feats, season, stored=P.load_kf_params())
    feats = P.add_components_static(feats)
    return P.add_gbm_components(feats)


def predict_frame(frame: pd.DataFrame, season: int, weeks: list[int]) -> pd.DataFrame:
    """Components + ensemble + simulator for the given unplayed weeks."""
    df = frame.copy()
    target = df[(df["season"] == season) & df["week"].isin(weeks) & ~df["played"]]
    train = df[df["played"] & df["result"].notna()]
    lgbm_pred, lgbm_contrib = gbm.fit_predict_with_contrib(
        train, target, feature_columns(False), False
    )
    df.loc[target.index, "lgbm_margin"] = lgbm_pred
    df.loc[target.index, "lgbm_mkt_margin"] = gbm.fit_predict(
        train, target, feature_columns(True), True
    )
    for c in ("lgbm", "lgbm_mkt"):
        df[f"{c}_prob"] = margin_to_prob(df[f"{c}_margin"])
    need = ["market_prob", "elo_prob", "kf_prob", "lgbm_prob", "lgbm_mkt_prob"]
    pool = df[df["played"] & (df["season"] >= C.WARMUP_SEASON)].dropna(subset=need)
    ens = Ensemble(pool)
    out = df.loc[target.index].copy()
    out[["ens_prob", "ens_margin", "ens_total"]] = ens.predict(out).to_numpy()
    nm = ens.no_market
    out["nomkt_prob"] = nm.prob(out)
    out["nomkt_margin"] = nm.margin(out)
    out["nomkt_total"] = nm.total(out)
    out.attrs["ensemble_weights"] = ens.weights()
    out.attrs["no_market_stack"] = nm
    out.attrs["lgbm_contrib"] = lgbm_contrib.loc[out.index]
    return out


def simulate_rows(rows: pd.DataFrame, n_sims: int = 20000) -> dict[str, np.ndarray]:
    """Simulations for the blended ensemble (keys as is) and for the model-only headline (mo_*).

    Also stores the raw model-only margin and total draws so the snapshot can include
    a histogram and the site never has to re-simulate.
    """
    out: dict[str, object] = {"n_sims": n_sims, "seed": 2026}
    for prefix, tcol, mcol, pcol in (
        ("", "ens_total", "ens_margin", "ens_prob"),
        ("mo_", "nomkt_total", "nomkt_margin", "nomkt_prob"),
    ):
        total = rows[tcol].to_numpy()
        margin = rows[mcol].to_numpy()
        h, a = simulate_games(
            (total + margin) / 2, (total - margin) / 2, n_sims=n_sims, seed=2026, params=SimParams()
        )
        res = summarize_sim(h, a)
        res.update(likely_score(h, a, rows[pcol].to_numpy() >= 0.5, margin))
        out.update({prefix + k: v for k, v in res.items()})
        if prefix == "mo_":
            out["mo_margin_draws"] = h - a
            out["mo_total_draws"] = h + a
    return out


def apply_news(rows: pd.DataFrame, now: str, root: Path | None = None) -> list[dict]:
    """Adjust ensemble prob/margin for players in ``news/``; returns audit records.

    The player value table is only built (two small downloads) if some news file exists.
    """
    cache: dict[tuple[int, int], list[dict]] = {}
    for key in {(int(r.season), int(r.week)) for r in rows.itertuples()}:
        cache[key] = N.load_news(N.news_path(*key, root=root))
    values = None
    if any(cache.values()):
        from ensemblitz import players as PL

        season = int(rows["season"].iloc[0])
        values = PL.build_values(*PL.load_raw(season), season)
    audits = []
    for idx, r in rows.iterrows():
        a = N.adjust_game(
            r["ens_prob"],
            r["ens_margin"],
            r["home_team"],
            r["away_team"],
            cache[(int(r["season"]), int(r["week"]))],
            values,
            as_of=now,
        )
        audits.append(a)
        if a["applied"]:
            rows.loc[idx, "ens_prob"] = a["prob_home_after"]
            rows.loc[idx, "ens_margin"] = a["margin_after"]
    return audits


def _f(x: float | None, nd: int = 4) -> float | None:
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def model_only_block(r: pd.Series, sim: dict[str, np.ndarray], i: int) -> dict:
    """The headline numbers: the stack of Elo, Kalman and LightGBM, with no market input."""
    m, t = float(r["nomkt_margin"]), float(r["nomkt_total"])
    return {
        "home_win_prob": _f(r["nomkt_prob"]),
        "margin": _f(m, 2),
        "total": _f(t, 2),
        "home_points": _f((t + m) / 2, 2),
        "away_points": _f((t - m) / 2, 2),
        "sim": {
            "p_home": _f(sim["mo_p_home"][i]),
            "home_q10": _f(sim["mo_home_q10"][i], 1),
            "home_q90": _f(sim["mo_home_q90"][i], 1),
            "away_q10": _f(sim["mo_away_q10"][i], 1),
            "away_q90": _f(sim["mo_away_q90"][i], 1),
            "margin_q10": _f(sim["mo_margin_q10"][i], 1),
            "margin_q90": _f(sim["mo_margin_q90"][i], 1),
            "total_q10": _f(sim["mo_total_q10"][i], 1),
            "total_q90": _f(sim["mo_total_q90"][i], 1),
        },
        "example_score": {
            "home": int(sim["mo_like_home"][i]),
            "away": int(sim["mo_like_away"][i]),
            "prob": _f(sim["mo_like_prob"][i]),
        },
    }


def game_record(
    r: pd.Series,
    sim: dict[str, np.ndarray],
    i: int,
    now: str,
    news_adj: dict | None = None,
    absences: dict[str, list[dict]] | None = None,
) -> dict:
    comps = {c: _f(r[f"{c}_prob"]) for c in ("market", "elo", "kf", "lgbm", "lgbm_mkt")}
    comps["ensemble"] = _f(r["ens_prob"])
    if news_adj and news_adj.get("applied"):
        comps["ensemble_pre_news"] = _f(news_adj["prob_home_before"])
    comps["ensemble_model_only"] = _f(r["nomkt_prob"])
    mo_home = bool(r["nomkt_prob"] >= 0.5)
    return {
        "game_id": r["game_id"],
        "season": int(r["season"]),
        "week": int(r["week"]),
        "home_team": r["home_team"],
        "away_team": r["away_team"],
        "kickoff_utc": r["kickoff_utc"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at": now,
        "model_version": C.MODEL_VERSION,
        "home_win_prob": comps,
        # The headline is the model on its own; the blended ensemble is kept for comparison.
        "headline": "model_only",
        "pick": r["home_team"] if mo_home else r["away_team"],
        "ensemble_pick": r["home_team"] if r["ens_prob"] >= 0.5 else r["away_team"],
        "model_only": model_only_block(r, sim, i),
        "predicted_margin": _f(r["ens_margin"], 2),
        "model_only_margin": _f(r["nomkt_margin"], 2),
        "predicted_total": _f(r["ens_total"], 2),
        "news_adjustment": news_adj or {"applied": False},
        # Context only: not part of any number (Phase 1 did not show a gain from injuries).
        "absences": {
            "home": (absences or {}).get(r["home_team"], []),
            "away": (absences or {}).get(r["away_team"], []),
        },
        "most_likely_score": {
            "home": int(sim["like_home"][i]),
            "away": int(sim["like_away"][i]),
            "prob": _f(sim["like_prob"][i]),
            "method": "nearest frequent score to the mean of simulations that match the pick and margin band",
            "raw_mode": {
                "home": int(sim["mode_home"][i]),
                "away": int(sim["mode_away"][i]),
                "prob": _f(sim["mode_prob"][i]),
            },
        },
        "sim": {
            "p_home": _f(sim["p_home"][i]),
            "margin_q10": _f(sim["margin_q10"][i], 1),
            "margin_q90": _f(sim["margin_q90"][i], 1),
            "total_q10": _f(sim["total_q10"][i], 1),
            "total_q90": _f(sim["total_q90"][i], 1),
        },
        "market": {
            "spread_line": _f(r["spread_line"], 1),
            "total_line": _f(r["total_line"], 1),
            "home_moneyline": _f(r["home_moneyline"], 0),
            "away_moneyline": _f(r["away_moneyline"], 0),
        },
        "context": {
            "home_qb_change": int(r["h_qb_change"]),
            "away_qb_change": int(r["a_qb_change"]),
            "home_rest": int(r["h_rest"]),
            "away_rest": int(r["a_rest"]),
            "dome": int(r["dome"]),
            "weather_known": int(r["weather_known"]),
            "temp": _f(r["temp"], 0) if r["weather_known"] else None,
            "wind": _f(r["wind"], 0) if r["weather_known"] else None,
            "home_out_lag": int(r["h_out_lag"]),
            "away_out_lag": int(r["a_out_lag"]),
        },
    }


def _absences(rows: pd.DataFrame) -> dict[tuple[int, int], dict[str, list[dict]]]:
    """Notable Out/Doubtful players per (season, week); empty if the inputs are not available."""
    from ensemblitz import impact as I

    out: dict[tuple[int, int], dict[str, list[dict]]] = {}
    try:
        data = I.load_inputs()
        for s, w in sorted({(int(r.season), int(r.week)) for r in rows.itertuples()}):
            out[(s, w)] = I.notable_absences(s, w, data=data)
    except (OSError, KeyError, ValueError) as exc:  # context is optional; never block a pick
        log.warning("absence context skipped: %s", exc)
    return out


def _binned_counts(values, lo: int, hi: int, width: int = 1) -> dict:
    import numpy as np

    v = np.clip(np.rint(np.asarray(values, float)), lo, hi)
    bins = np.arange(lo, hi + 1, width)
    counts = [int((v == b).sum()) for b in bins]
    return {"lo": lo, "width": width, "counts": counts}


def _odds_quotes() -> dict[tuple[str, str], dict]:
    """Latest cached Odds API consensus, keyed by (home, away). Empty if there is no cache."""
    from ensemblitz.odds import client
    from ensemblitz.odds.report import consensus_for_teams

    odds = client.latest_cache()
    if odds is None or odds.empty:
        return {}
    fetched = str(odds["fetched_at"].iloc[0]) if "fetched_at" in odds.columns else None
    out: dict[tuple[str, str], dict] = {}
    from ensemblitz.odds.report import book_probs

    bp = book_probs(odds)
    if bp.empty:
        return {}
    for home, away in bp[["home", "away"]].drop_duplicates().itertuples(index=False):
        rec = consensus_for_teams(odds, home, away)
        if rec:
            rec = {**rec, "fetched_at": rec.get("fetched_at") or fetched}
            out[(home, away)] = rec
    return out


def _market_block(r: pd.Series, now: str, quotes: dict[tuple[str, str], dict]) -> list[dict]:
    market = [
        {
            "source": "nflverse_line",
            "captured_at_utc": now,
            "is_closing": False,
            "home_win_prob": _f(r["market_prob"]),
            "margin_home": _f(r["spread_line"], 1),
            "total_line": _f(r["total_line"], 1),
            "home_moneyline": _f(r["home_moneyline"], 0),
            "away_moneyline": _f(r["away_moneyline"], 0),
        }
    ]
    rec = quotes.get((r["home_team"], r["away_team"]))
    if rec and rec.get("consensus_home_prob_shin") is not None:
        market.append(
            {
                "source": "odds_api_consensus",
                "captured_at_utc": rec.get("fetched_at") or now,
                "is_closing": False,
                "home_win_prob": rec["consensus_home_prob_shin"],
                "margin_home": None,
                "total_line": None,
                "n_books": rec.get("n_books"),
            }
        )
    return market


def _news_v1(news_adj: dict | None) -> dict:
    na = news_adj or {"applied": False}
    out = {"applied": bool(na.get("applied")), "applies_to": "ensemble"}
    if not na.get("applied") and "margin_points" not in na:
        return out
    for src, dst in (
        ("margin_points", "margin_points"),
        ("home_points_lost", "home_points_lost"),
        ("away_points_lost", "away_points_lost"),
        ("prob_home_before", "home_win_prob_before"),
        ("margin_before", "margin_home_before"),
    ):
        if src in na:
            out[dst] = na[src]
    if "items" in na:
        out["items"] = na["items"]
    return out


def v1_game_record(
    r: pd.Series,
    sim: dict[str, np.ndarray],
    i: int,
    now: str,
    news_adj: dict | None,
    absences: dict[str, list[dict]] | None,
    quotes: dict[tuple[str, str], dict],
    explanation: dict | None = None,
) -> dict:
    """One v1 game record. The headline is the model on its own."""
    components = {c: _f(r[f"{c}_prob"]) for c in ("elo", "kf", "lgbm", "lgbm_mkt")}
    hist = None
    if "mo_margin_draws" in sim:
        hist = {
            "margin_home": _binned_counts(sim["mo_margin_draws"][i], -35, 35),
            "total": _binned_counts(sim["mo_total_draws"][i], 10, 80),
        }
    distribution = {
        "n_sims": int(sim.get("n_sims", 20000)),
        "seed": int(sim.get("seed", 2026)),
        "p_home": _f(sim["mo_p_home"][i]),
        "home_points": [_f(sim["mo_home_q10"][i], 1), _f(sim["mo_home_q90"][i], 1)],
        "away_points": [_f(sim["mo_away_q10"][i], 1), _f(sim["mo_away_q90"][i], 1)],
        "margin_home": [_f(sim["mo_margin_q10"][i], 1), _f(sim["mo_margin_q90"][i], 1)],
        "total": [_f(sim["mo_total_q10"][i], 1), _f(sim["mo_total_q90"][i], 1)],
    }
    if hist is not None:
        distribution["histogram"] = hist
    bands = None
    if "mo_margin_draws" in sim:
        bands = OB.from_margins(
            sim["mo_margin_draws"][i],
            int(sim.get("n_sims", 20000)),
            int(sim.get("seed", 2026)),
        )
    m, tot = float(r["nomkt_margin"]), float(r["nomkt_total"])
    return {
        "game_id": r["game_id"],
        "home_team": r["home_team"],
        "away_team": r["away_team"],
        "kickoff_utc": r["kickoff_utc"].strftime("%Y-%m-%dT%H:%M:%SZ")
        if hasattr(r["kickoff_utc"], "strftime")
        else str(r["kickoff_utc"]),
        "generated_at_utc": now,
        "headline": {
            "home_win_prob": _f(r["nomkt_prob"]),
            "home_points": _f((tot + m) / 2, 2),
            "away_points": _f((tot - m) / 2, 2),
            "distribution": distribution,
            "example_score": {
                "home": int(sim["mo_like_home"][i]),
                "away": int(sim["mo_like_away"][i]),
                "prob": _f(sim["mo_like_prob"][i]),
            },
        },
        "ensemble": {
            "home_win_prob": _f(r["ens_prob"]),
            "margin_home": _f(r["ens_margin"], 2),
            "total": _f(r["ens_total"], 2),
        },
        "components": components,
        "market": _market_block(r, now, quotes),
        "context": {
            "home_qb_change": bool(r["h_qb_change"]),
            "away_qb_change": bool(r["a_qb_change"]),
            "home_rest_days": int(r["h_rest"]),
            "away_rest_days": int(r["a_rest"]),
            "dome": bool(r["dome"]),
            "weather_known": bool(r["weather_known"]),
            "temp_f": _f(r["temp"], 0) if r["weather_known"] else None,
            "wind_mph": _f(r["wind"], 0) if r["weather_known"] else None,
            "home_out_lag": int(r["h_out_lag"]),
            "away_out_lag": int(r["a_out_lag"]),
        },
        "absences": {
            "home": (absences or {}).get(r["home_team"], []),
            "away": (absences or {}).get(r["away_team"], []),
        },
        "news_adjustment": _news_v1(news_adj),
        **({"outcome_bands": bands} if bands is not None else {}),
        **({"explanation": explanation} if explanation is not None else {}),
    }


def run_predict(
    season: int,
    week: int | None = None,
    n_weeks: int = 1,
    use_news: bool = True,
    *,
    force: bool = False,
    production: bool = False,
    root: Path | None = None,
    now: datetime | None = None,
) -> list[Path]:
    """Write a new immutable v1 snapshot for each requested week (never overwrites).

    Any game in the target week with ``kickoff_utc <= now`` is automatically frozen to
    its exact canonical record from the latest snapshot published strictly before that
    game's kickoff.
    """
    now_dt = (now or datetime.now(UTC)).astimezone(UTC)
    frame = build_frame(season)
    weeks = [week] if week else open_next_weeks(frame, season, n_weeks, now=now_dt, root=root)
    if not weeks:
        log.info("no open unplayed weeks in %s", season)
        return []
    for w in weeks:
        wk_kicks = _week_kickoffs(frame, season, w)
        if L.week_is_locked(season, w, now=now_dt, root=root, games=wk_kicks):
            last = L.last_kickoff_utc(season, w, root, wk_kicks)
            raise L.WeekLockedError(
                f"{season} week {w} is locked: all games have passed kickoff (last kickoff {last}). "
                "A historical correction follows docs/LEDGER.md; --force cannot unlock it."
            )
    rows = predict_frame(frame, season, weeks)
    now_str = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    weights = rows.attrs.get("ensemble_weights", {})
    no_market_stack = rows.attrs.get("no_market_stack")
    lgbm_contrib = rows.attrs.get("lgbm_contrib")
    if lgbm_contrib is not None:
        lgbm_contrib = lgbm_contrib.reset_index(drop=True)
    rows = rows.reset_index(drop=True)
    audits = apply_news(rows, now_str) if use_news else [None] * len(rows)
    sim = simulate_rows(rows)
    ab = _absences(rows)
    quotes = _odds_quotes()
    prov = K.provenance(root, production=production)
    cutoff = K.data_cutoff_utc(root=root, now=now_dt)
    snapshot = K.data_snapshot(root=root)
    recs = []
    for i, r in rows.iterrows():
        wk_ab = ab.get((int(r["season"]), int(r["week"])))
        game_ab = {
            "home": (wk_ab or {}).get(r["home_team"], []),
            "away": (wk_ab or {}).get(r["away_team"], []),
        }
        expl = (
            X.build_game_explanation(r, lgbm_contrib.iloc[i], no_market_stack, game_ab, cutoff)
            if (no_market_stack is not None and lgbm_contrib is not None)
            else None
        )
        recs.append(v1_game_record(r, sim, i, now_str, audits[i], wk_ab, quotes, expl))
    # data_cutoff cannot be later than the run; clamp only if equal clocks differ by rounding
    if cutoff > now_str:
        raise K.ContractError(f"data_cutoff_utc {cutoff} is later than generated_at_utc {now_str}")
    paths = []
    for w in weeks:
        week_games = [g for g in recs if _week_of(g) == w]
        week_games = L.freeze_started_games(season, w, week_games, now=now_dt, root=root)
        doc = {
            "schema_version": K.SCHEMA_VERSION,
            "model_version": C.MODEL_VERSION,
            "git_sha": prov["git_sha"],
            "reproducible": prov["reproducible"],
            "generated_at_utc": now_str,
            "data_cutoff_utc": cutoff,
            "data_snapshot": snapshot,
            "season": season,
            "week": w,
            "ensemble_weights": weights,
            "games": week_games,
        }
        errors = K.validate_week(doc)
        if errors:
            raise K.ContractError("invalid v1 snapshot: " + "; ".join(errors[:8]))
        paths.append(L.write_snapshot(doc, root=root, force=force, now=now_dt))
    return paths


def _week_of(g: dict) -> int:
    return int(g["game_id"].split("_")[1])


__all__ = ["has_open_games", "open_next_weeks", "pred_path", "run_predict"]
