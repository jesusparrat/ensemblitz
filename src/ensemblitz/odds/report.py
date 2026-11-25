"""Discrepancy report: our ensemble versus every sportsbook and their consensus."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from scipy.special import ndtr

from ensemblitz import config as C
from ensemblitz.odds import client, devig
from ensemblitz.odds.teams import NAME_TO_ABBR

BIG_EDGE = 0.05
MARGIN_SD = 13.0


def book_probs(odds: pd.DataFrame) -> pd.DataFrame:
    """Per event and bookmaker: fair home win probability (multiplicative and Shin) and prices."""
    h2h = odds[odds["market"] == "h2h"].copy()
    h2h["home"] = h2h["home_name"].map(NAME_TO_ABBR)
    h2h["away"] = h2h["away_name"].map(NAME_TO_ABBR)
    rows = []
    for (ev, bk), d in h2h.groupby(["event_id", "bookmaker"]):
        r0 = d.iloc[0]
        ph = d[d["outcome"] == r0["home_name"]]["price"]
        pa = d[d["outcome"] == r0["away_name"]]["price"]
        if ph.empty or pa.empty:
            continue
        o = np.array([ph.iloc[0], pa.iloc[0]], float)
        rows.append(
            {
                "event_id": ev,
                "bookmaker": bk,
                "home": r0["home"],
                "away": r0["away"],
                "commence_time": r0["commence_time"],
                "home_price": o[0],
                "away_price": o[1],
                "p_home_mult": devig.multiplicative(o)[0],
                "p_home_shin": devig.shin(o)[0],
                "overround": devig.overround(o),
            }
        )
    return pd.DataFrame(rows)


def lines(odds: pd.DataFrame) -> pd.DataFrame:
    """Consensus (median) spread and total per event."""
    sp = odds[odds["market"] == "spreads"].copy()
    sp = sp[sp["outcome"] == sp["home_name"]]
    tot = odds[(odds["market"] == "totals") & (odds["outcome"] == "Over")]
    a = sp.groupby("event_id")["point"].median().rename("book_spread_home")  # negative = home fav
    b = tot.groupby("event_id")["point"].median().rename("book_total")
    return pd.concat([a, b], axis=1).reset_index()


def consensus_for_teams(odds: pd.DataFrame, home: str, away: str) -> dict | None:
    """Shin consensus and median lines for one matchup, with no need for a prediction file."""
    bp = book_probs(odds)
    if bp.empty:
        return None
    m = bp[(bp["home"] == home) & (bp["away"] == away)]
    if m.empty:
        return None
    ln = lines(odds)
    ev = m["event_id"].iloc[0]
    ln_g = ln[ln["event_id"] == ev]
    rec = {
        "consensus_home_prob_shin": round(float(m["p_home_shin"].mean()), 4),
        "n_books": int(len(m)),
        "fetched_at": str(odds["fetched_at"].iloc[0]) if "fetched_at" in odds.columns else None,
    }
    if not ln_g.empty:
        bs = ln_g["book_spread_home"].iloc[0]
        rec["book_spread_home"] = None if pd.isna(bs) else float(bs)
        rec["book_total"] = (
            None if pd.isna(ln_g["book_total"].iloc[0]) else float(ln_g["book_total"].iloc[0])
        )
    return rec


def explain(g: dict, edge: float) -> list[str]:
    """Plausible reasons for a disagreement, using only data we hold."""
    c = g["context"]
    why = []
    if c["home_qb_change"] or c["away_qb_change"]:
        side = "local" if c["home_qb_change"] else "visitante"
        why.append(
            f"cambio de QB titular ({side}); el mercado suele ajustarlo más rápido que nuestros ratings"
        )
    if abs(c["home_rest"] - c["away_rest"]) >= 3:
        why.append(f"descanso desigual ({c['home_rest']} vs {c['away_rest']} días)")
    if not c["dome"] and c.get("weather_known", 1) and (c["wind"] or 0) >= 15:
        why.append(
            f"viento fuerte ({c['wind'] * 1.609:.0f} km/h): baja el total y favorece al equipo que corre"
        )
    if (
        not c["dome"]
        and c.get("weather_known", 1)
        and (c["temp"] if c["temp"] is not None else 60) <= 32
    ):
        why.append(f"frío extremo ({(c['temp'] - 32) / 1.8:.0f} °C)")
    if abs(c["home_out_lag"] - c["away_out_lag"]) >= 3:
        why.append(
            f"bajas distintas en el último parte (local {c['home_out_lag']}, visitante {c['away_out_lag']})"
        )
    if not why:
        why.append(
            "sin causa clara en nuestros datos: lo más probable es información que el modelo no ve "
            "(lesiones de última hora, movimientos de apuestas profesionales)"
        )
    return why


def _game_view(g: dict) -> dict:
    """v0 or v1 game → the fields ``build`` and ``explain`` already use."""
    if "home_win_prob" in g and isinstance(g["home_win_prob"], dict):
        return g
    # v1
    c = g["context"]
    return {
        "game_id": g["game_id"],
        "home_team": g["home_team"],
        "away_team": g["away_team"],
        "kickoff_utc": g["kickoff_utc"],
        "predicted_margin": g["ensemble"]["margin_home"],
        "home_win_prob": {
            "ensemble": g["ensemble"]["home_win_prob"],
            "ensemble_model_only": g["headline"]["home_win_prob"],
            **{k: g["components"].get(k) for k in ("elo", "kf", "lgbm", "lgbm_mkt")},
        },
        "context": {
            "home_qb_change": int(c["home_qb_change"]),
            "away_qb_change": int(c["away_qb_change"]),
            "home_rest": int(c["home_rest_days"]),
            "away_rest": int(c["away_rest_days"]),
            "dome": int(c["dome"]),
            "weather_known": int(c["weather_known"]),
            "temp": c["temp_f"],
            "wind": c["wind_mph"],
            "home_out_lag": int(c["home_out_lag"]),
            "away_out_lag": int(c["away_out_lag"]),
        },
    }


def build(pred: dict, odds: pd.DataFrame, fetched_at: str | None) -> dict:
    bp = book_probs(odds)
    ln = lines(odds)
    games = []
    for raw in pred["games"]:
        g = _game_view(raw)
        m = bp[(bp["home"] == g["home_team"]) & (bp["away"] == g["away_team"])]
        if m.empty:
            continue
        ours = g["home_win_prob"]["ensemble"]
        cons = float(m["p_home_shin"].mean())
        ev = m["event_id"].iloc[0]
        ln_g = ln[ln["event_id"] == ev]
        books = {
            r.bookmaker: {
                "p_home_shin": round(r.p_home_shin, 4),
                "p_home_mult": round(r.p_home_mult, 4),
                "home_price": r.home_price,
                "away_price": r.away_price,
                "edge_vs_ours": round(ours - r.p_home_shin, 4),
            }
            for r in m.itertuples()
        }
        best_h = m.loc[m["home_price"].idxmax()]
        best_a = m.loc[m["away_price"].idxmax()]
        ev_home = ours * best_h["home_price"] - 1
        ev_away = (1 - ours) * best_a["away_price"] - 1
        side = "home" if ev_home >= ev_away else "away"
        edge = ours - cons
        # The published ensemble leans on the market, so its distance to the market is small by
        # construction. The informative gap is the one between the market and our models alone.
        pure = g["home_win_prob"].get("ensemble_model_only")
        gap = None if pure is None else pure - cons
        flagged = abs(edge if gap is None else gap) >= BIG_EDGE
        rec = {
            "game_id": g["game_id"],
            "home": g["home_team"],
            "away": g["away_team"],
            "kickoff_utc": g["kickoff_utc"],
            "our_home_prob": ours,
            "consensus_home_prob_shin": round(cons, 4),
            "consensus_home_prob_mult": round(float(m["p_home_mult"].mean()), 4),
            "edge": round(edge, 4),
            "model_only_home_prob": None if pure is None else round(pure, 4),
            "gap_model_only": None if gap is None else round(gap, 4),
            "n_books": int(len(m)),
            "best_home_price": {"book": best_h["bookmaker"], "price": float(best_h["home_price"])},
            "best_away_price": {"book": best_a["bookmaker"], "price": float(best_a["away_price"])},
            "ev_per_unit_best": {
                "home": round(float(ev_home), 4),
                "away": round(float(ev_away), 4),
            },
            "best_side": side,
            "flag_large_disagreement": flagged,
            "books": books,
        }
        if not ln_g.empty:
            bs = ln_g["book_spread_home"].iloc[0]
            rec["book_spread_home"] = None if pd.isna(bs) else float(bs)
            rec["book_total"] = (
                None if pd.isna(ln_g["book_total"].iloc[0]) else float(ln_g["book_total"].iloc[0])
            )
            if rec["book_spread_home"] is not None and g["predicted_margin"] is not None:
                rec["our_margin_minus_book"] = round(
                    g["predicted_margin"] + rec["book_spread_home"], 2
                )
                rec["our_cover_prob_home"] = round(
                    float(ndtr((g["predicted_margin"] + rec["book_spread_home"]) / MARGIN_SD)), 4
                )
        if rec["flag_large_disagreement"]:
            rec["likely_reasons"] = explain(g, edge)
        games.append(rec)
    return {
        "season": pred["season"],
        "week": pred["week"],
        "odds_fetched_at": fetched_at,
        "predictions_generated_at": pred.get("generated_at_utc") or pred.get("generated_at"),
        "games": games,
    }


def to_markdown(rep: dict) -> str:
    L = [
        f"# Cuotas vs modelo, {rep['season']} semana {rep['week']}",
        "",
        f"Cuotas descargadas: {rep['odds_fetched_at']}. Picks generados: {rep['predictions_generated_at']}.",
        "Probabilidades sin margen del casino (Shin). Edge = prob. nuestra − prob. consenso (local). "
        "EV = valor esperado por unidad apostada al mejor precio disponible, si nuestra probabilidad fuese la correcta.",
        "",
        "| Partido | Nuestra | Consenso | Edge | Mejor lado | Mejor precio | EV | Casas |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for g in sorted(rep["games"], key=lambda x: -abs(x["edge"])):
        side = g["best_side"]
        bp = g["best_home_price" if side == "home" else "best_away_price"]
        team = g["home"] if side == "home" else g["away"]
        flag = " ⚠" if g["flag_large_disagreement"] else ""
        L.append(
            f"| {g['away']} @ {g['home']}{flag} | {g['our_home_prob'] * 100:.1f}% | "
            f"{g['consensus_home_prob_shin'] * 100:.1f}% | {g['edge'] * 100:+.1f} pp | {team} | "
            f"{bp['price']:.2f} ({bp['book']}) | {g['ev_per_unit_best'][side] * 100:+.1f}% | {g['n_books']} |"
        )
    flagged = [g for g in rep["games"] if g["flag_large_disagreement"]]
    if flagged:
        L += ["", "## Banderas: solo modelos frente al consenso (≥ 5 pp)", ""]
        for g in flagged:
            gap = g.get("gap_model_only")
            if gap is None:
                gap = g["edge"]
            L.append(
                f"- **{g['away']} @ {g['home']}**: brecha {gap * 100:+.1f} pp (local). "
                + "; ".join(g["likely_reasons"])
                + "."
            )
    L += [
        "",
        "Aviso: el mercado de cierre es muy eficiente; en el backtest nuestro modelo no lo supera "
        "(ver `reports/backtest.md`). Un EV positivo aquí es una hipótesis del modelo, no una garantía.",
    ]
    return "\n".join(L) + "\n"


def _latest_pred(season: int, week: int) -> dict | None:
    """Load the current snapshot for a week (legacy path or ledger), or None."""
    from ensemblitz import ledger as L

    art = L.latest_artifact(season, week)
    path = art.path if art is not None else L.legacy_week_path(season, week)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _weeks_to_report(season: int, week: int | None, now: str) -> list[int]:
    """The requested week, or every predicted week that still has a game to play."""
    from ensemblitz import ledger as L

    if week is not None:
        return [week]
    out = []
    for art in L.iter_latest():
        if art.season != season:
            continue
        d = json.loads(art.path.read_text())
        if any(g["kickoff_utc"] > now for g in d["games"]):
            out.append(int(d.get("week", art.week)))
    return out


def run_odds(season: int, week: int | None, fetch: bool = True, report: bool = True) -> str:
    """Fetch (optional) then, if predictions exist, write the comparison report.

    Fetching does not need predictions, so the weekly job can call this *before*
    ``ensemblitz predict`` and freeze the consensus with the snapshot. The report
    is written afterwards from the cache (``fetch=False``), without a second API call.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if fetch:
        odds, status = client.fetch_odds()
    else:
        odds, status = client.latest_cache(), "live fetch disabled"
    if odds is None or (hasattr(odds, "empty") and odds.empty):
        return f"Odds report skipped: {status}."
    if not report:
        n = (
            0
            if odds is None
            else (odds["event_id"].nunique() if "event_id" in odds.columns else len(odds))
        )
        return f"{status}. Cache ready ({n} events); report skipped."
    weeks = _weeks_to_report(season, week, now)
    if not weeks:
        return f"{status}. No predictions found: report skipped (run `ensemblitz predict` then `ensemblitz odds --no-fetch`)."
    fetched = str(odds["fetched_at"].iloc[0]) if "fetched_at" in odds.columns else None
    out = C.REPORTS_DIR / "odds"
    out.mkdir(parents=True, exist_ok=True)
    msgs = []
    for w in weeks:
        pred = _latest_pred(season, w)
        if pred is None:
            msgs.append(f"week {w}: no snapshot")
            continue
        rep = build(pred, odds, fetched)
        if not rep["games"]:
            continue
        stem = out / f"{season}_week{w:02d}"
        stem.with_suffix(".json").write_text(json.dumps(rep, indent=1))
        stem.with_suffix(".md").write_text(to_markdown(rep))
        msgs.append(f"week {w}: {len(rep['games'])} games")
    return f"{status}. Wrote {C.REPORTS_DIR / 'odds'} ({'; '.join(msgs) or 'no games matched'})"
