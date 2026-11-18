"""Walk-forward gates for the drive-level simulator with a clutch window.

The published model is not changed. A gate that fails is reported and the
simulator stays behind ``ensemblitz pbp``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from scipy.stats import wasserstein_distance
from sklearn.linear_model import LogisticRegression

from ensemblitz import config as C
from ensemblitz.baseline import load_cache, score, walk_forward
from ensemblitz.sim.drive import simulate_games
from ensemblitz.sim.drive_fit import load_drives, rates_before
from ensemblitz.sim.hybrid import from_book, simulate

REPORT_MD = C.REPORTS_DIR / "PBP_SIM.md"
REPORT_JSON = C.REPORTS_DIR / "pbp_sim_2018_2025.json"
MODEL_ONLY_BAR = 0.6344
BOOT_N = 10_000
BOOT_SEED = 202603


def walk_scores(
    drives: pd.DataFrame,
    games: pd.DataFrame,
    n_sims: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Scores aligned to ``games`` row order. Rates stop before each week."""
    home = np.zeros((len(games), n_sims), np.int64)
    away = np.zeros((len(games), n_sims), np.int64)
    games = games.reset_index(drop=True)
    for (season, week), idx in games.groupby(["season", "week"]).groups.items():
        ix = np.asarray(list(idx))
        g = games.loc[ix]
        book = rates_before(drives, int(season), int(week))
        match = from_book(book, g["home"].to_numpy(), g["away"].to_numpy(), g["season"].to_numpy())
        h, a = simulate(match, n_sims=n_sims, seed=seed + int(season) * 100 + int(week))
        home[ix] = h
        away[ix] = a
    return home, away


def _keys(margin: np.ndarray) -> dict[str, float]:
    flat = np.abs(np.asarray(margin)).ravel()
    return {str(k): float(np.mean(flat == k)) for k in (3, 7, 10)}


def _ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> list[dict]:
    order = np.argsort(p)
    ps, ys = p[order], y[order]
    edges = np.linspace(0, len(ps), bins + 1).astype(int)
    rows = []
    for i in range(bins):
        lo, hi = int(edges[i]), int(edges[i + 1])
        if hi <= lo:
            continue
        pred, act = float(ps[lo:hi].mean()), float(ys[lo:hi].mean())
        rows.append(
            {"bin": i + 1, "n": hi - lo, "pred": pred, "actual": act, "weight": (hi - lo) / len(ps)}
        )
    return rows


def _top_error(p: np.ndarray, y: np.ndarray) -> dict:
    m = p >= 0.80
    if not np.any(m):
        return {"n": 0, "pred": None, "actual": None, "abs_error": None}
    pred, act = float(p[m].mean()), float(y[m].mean())
    return {"n": int(m.sum()), "pred": pred, "actual": act, "abs_error": abs(pred - act)}


def _logit_ll(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _linear_over(frame: pd.DataFrame) -> np.ndarray:
    """Walk-forward P(over) from a logistic regression on the closing total alone."""
    out = np.full(len(frame), np.nan)
    push = frame["actual_total"].to_numpy() == frame["total_line"].to_numpy()
    y_over = frame["actual_total"].to_numpy() > frame["total_line"].to_numpy()
    for (season, week), idx in frame.groupby(["season", "week"]).groups.items():
        ix = np.asarray(list(idx))
        earlier = (
            (frame["season"] < season) | ((frame["season"] == season) & (frame["week"] < week))
        ).to_numpy()
        train = earlier & ~push & np.isfinite(frame["total_line"].to_numpy())
        if y_over[train].sum() < 5 or (~y_over[train]).sum() < 5:
            continue
        clf = LogisticRegression(C=1e6, solver="lbfgs")
        clf.fit(frame.loc[train, ["total_line"]], y_over[train].astype(int))
        out[ix] = clf.predict_proba(frame.loc[ix, ["total_line"]])[:, 1]
    return out


def _boot_diff(a: np.ndarray, b: np.ndarray, n: int = BOOT_N) -> dict:
    rng = np.random.default_rng(BOOT_SEED)
    diff = a - b
    acc = []
    done = 0
    while done < n:
        bsz = min(1000, n - done)
        ix = rng.integers(0, len(diff), size=(bsz, len(diff)))
        acc.append(diff[ix].mean(axis=1))
        done += bsz
    s = np.concatenate(acc)
    return {
        "diff": float(diff.mean()),
        "ci": [float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))],
    }


def _actual_teams(drives: pd.DataFrame) -> pd.DataFrame:
    g = (
        drives[drives["is_home"] == 1]
        .groupby("game_id", as_index=False)
        .agg(home=("team", "first"))
    )
    a = (
        drives[drives["is_home"] == 0]
        .groupby("game_id", as_index=False)
        .agg(away=("team", "first"))
    )
    out = g.merge(a, on="game_id", how="inner")
    path = C.PROC_DIR / "pbp_sim" / "actuals.parquet"
    if path.exists():
        act = pd.read_parquet(path)[["game_id", "home_score", "away_score"]]
        out = out.merge(act, on="game_id", how="left")
    return out


def evaluate(n_sims: int = 2000, seed: int = 202603) -> dict:
    drives = load_drives()
    cache = walk_forward(load_cache())[0]
    games = cache[cache["season"].between(C.FIRST_BACKTEST_SEASON, C.LAST_BACKTEST_SEASON)].copy()
    games = games[games["week"] <= 18].dropna(
        subset=["result", "market_prob", "model_only_prob", "model_only_margin", "kf_total"]
    )
    games = games.merge(_actual_teams(drives), on="game_id", how="inner")
    games = games.dropna(subset=["home", "away", "home_score", "away_score"]).reset_index(drop=True)
    home, away = walk_scores(drives, games, n_sims, seed)
    margin = home - away
    total = home + away
    decided = games["result"].to_numpy() != 0
    y = (games.loc[decided, "result"].to_numpy() > 0).astype(float)
    wins = (home[decided] > away[decided]).mean(axis=1)
    losses = (away[decided] > home[decided]).mean(axis=1)
    p_cond = wins / np.maximum(wins + losses, 1e-9)
    sim_ll = score(p_cond, y)
    mo = games.loc[decided, "model_only_prob"].to_numpy(float)
    mk = games.loc[decided, "market_prob"].to_numpy(float)
    mo_ll = score(mo, y)
    mk_ll = score(mk, y)
    eh = ((games["kf_total"] + games["model_only_margin"]) / 2).to_numpy(float)
    ea = ((games["kf_total"] - games["model_only_margin"]) / 2).to_numpy(float)
    cur_h, cur_a = simulate_games(eh, ea, n_sims=n_sims, seed=seed)
    act_margin = games["result"].to_numpy(float)
    act_total = (games["home_score"] + games["away_score"]).to_numpy(float)
    w_margin = {
        "hybrid": float(wasserstein_distance(margin.ravel(), act_margin)),
        "current_drive": float(wasserstein_distance((cur_h - cur_a).ravel(), act_margin)),
    }
    w_total = {
        "hybrid": float(wasserstein_distance(total.ravel(), act_total)),
        "current_drive": float(wasserstein_distance((cur_h + cur_a).ravel(), act_total)),
    }
    frame = games.copy()
    frame["actual_total"] = act_total
    frame["p_over"] = (total > frame["total_line"].to_numpy(float)[:, None]).mean(axis=1)
    p_lin = _linear_over(frame)
    push = frame["actual_total"].to_numpy() == frame["total_line"].to_numpy()
    use = ~push & np.isfinite(p_lin) & frame["total_line"].notna().to_numpy()
    y_over = (
        (frame.loc[use, "actual_total"] > frame.loc[use, "total_line"]).astype(float).to_numpy()
    )
    over = {
        "n": int(use.sum()),
        "simulator": _logit_ll(frame.loc[use, "p_over"].to_numpy(float), y_over),
        "linear_on_closing_total": _logit_ll(p_lin[use], y_over),
    }
    rows = _ece(p_cond, y)
    ece = float(sum(r["weight"] * abs(r["pred"] - r["actual"]) for r in rows))
    top = _top_error(p_cond, y)
    keys = _keys(margin)
    sd = float(margin.std())
    gates = {
        "margin_sd": sd,
        "margin_sd_ok": 13.0 <= sd <= 14.2,
        "margin_3": keys["3"],
        "margin_3_ok": 0.13 <= keys["3"] <= 0.15,
        "margin_7": keys["7"],
        "margin_7_ok": 0.08 <= keys["7"] <= 0.10,
        "over_under_ok": over["simulator"] <= over["linear_on_closing_total"] + 1e-9,
        "win_prob_log_loss": sim_ll["log_loss"],
        "model_only_log_loss": mo_ll["log_loss"],
        "beats_model_only_0_6344": bool(sim_ll["log_loss"] < MODEL_ONLY_BAR),
        "ece": ece,
        "ece_ok": ece < 0.020,
        "top_bin_abs_error": top["abs_error"],
        "top_bin_ok": top["abs_error"] is not None and top["abs_error"] < 0.03,
    }
    gates["eligible_for_production"] = bool(
        gates["beats_model_only_0_6344"]
        and gates["ece_ok"]
        and gates["top_bin_ok"]
        and gates["margin_sd_ok"]
        and gates["margin_3_ok"]
        and gates["margin_7_ok"]
        and gates["over_under_ok"]
    )
    pclip = np.clip(p_cond, 1e-4, 1 - 1e-4)
    mclip = np.clip(mo, 1e-4, 1 - 1e-4)
    ll_vs_mo = _boot_diff(
        -(y * np.log(pclip) + (1 - y) * np.log(1 - pclip)),
        -(y * np.log(mclip) + (1 - y) * np.log(1 - mclip)),
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seasons": [int(C.FIRST_BACKTEST_SEASON), int(C.LAST_BACKTEST_SEASON)],
        "n_games": int(len(games)),
        "n_decided": int(decided.sum()),
        "n_sims": n_sims,
        "seed": seed,
        "gates": gates,
        "shape": {
            "margin_sd": sd,
            "actual_margin_sd": float(np.std(act_margin := act_margin_of(games))),
            "total_mean": float(total.mean()),
            "actual_total_mean": float(np.mean(act_total)),
            "home_margin": float(margin.mean()),
            "actual_home_margin": float(np.mean(act_margin)),
            "keys": keys,
            "actual_keys": _keys(act_margin),
        },
        "wasserstein": {"margin": w_margin, "total": w_total},
        "win_prob": {
            "simulator": sim_ll,
            "model_only": mo_ll,
            "market": mk_ll,
            "simulator_minus_model_only_log_loss": ll_vs_mo,
        },
        "over_under": over,
        "calibration": {"ece": ece, "deciles": rows, "top_bin": top},
    }


def act_margin_of(games: pd.DataFrame) -> np.ndarray:
    return games["result"].to_numpy(float)


def finite(o: object) -> object:
    if isinstance(o, dict):
        return {str(k): finite(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [finite(v) for v in o]
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


def render(payload: dict) -> str:
    g = payload["gates"]
    sh = payload["shape"]
    w = payload["wasserstein"]
    wp = payload["win_prob"]
    ov = payload["over_under"]
    top = payload["calibration"]["top_bin"]
    diff = wp["simulator_minus_model_only_log_loss"]
    failed = []
    if not g["margin_sd_ok"]:
        failed.append("margin_sd")
    if not g["margin_3_ok"]:
        failed.append("margin_3")
    if not g["margin_7_ok"]:
        failed.append("margin_7")
    if not g["over_under_ok"]:
        failed.append("over_under")
    if not g["beats_model_only_0_6344"]:
        failed.append("win_prob_log_loss")
    if not g["ece_ok"]:
        failed.append("ece")
    if not g["top_bin_ok"]:
        failed.append("top_bin")
    if g["eligible_for_production"]:
        verdict = (
            f"Every acceptance gate is inside its band, including a win-probability log loss "
            f"below {MODEL_ONLY_BAR:.4f}. It is eligible to be wired into production later. "
            "This change does not do that wiring."
        )
    else:
        verdict = (
            "The simulator is not eligible for production. Failed gates: "
            + ", ".join(failed)
            + ". It stays behind `ensemblitz pbp` and is not connected to the published picks."
        )
    lines = [
        "# Drive-level simulator with a clutch window",
        "",
        f"Generated {payload['generated_at']}. Walk-forward regular season "
        f"{payload['seasons'][0]}-{payload['seasons'][1]}, {payload['n_games']} games, "
        f"{payload['n_sims']} simulations, seed {payload['seed']}. "
        "Rates use only earlier weeks. Command: `ensemblitz pbp --evaluate`.",
        "",
        "## Verdict",
        "",
        verdict,
        "",
        "Most of a game is one draw per possession: touchdown, field goal, punt, turnover "
        "or end of half, opponent-adjusted and shrunk, with a longer drive when leading. "
        "Play-by-play is only the last four minutes of the fourth quarter and the last two "
        "minutes of the first half, and only when the margin is within 8. A touchdown is 7. "
        "In a tied game the field-goal share is raised. That weight was set on 2017 and not touched after.",
        "",
        "## Gates",
        "",
        "| Gate | Value | Band | Pass |",
        "|---|---|---|---|",
        f"| Margin SD | {g['margin_sd']:.2f} | 13.0 to 14.2 | {g['margin_sd_ok']} |",
        f"| Share of margins of 3 | {g['margin_3']:.3f} | 0.13 to 0.15 | {g['margin_3_ok']} |",
        f"| Share of margins of 7 | {g['margin_7']:.3f} | 0.08 to 0.10 | {g['margin_7_ok']} |",
        f"| Over/under log loss vs linear model | {ov['simulator']:.4f} vs {ov['linear_on_closing_total']:.4f} | simulator not worse | {g['over_under_ok']} |",
        f"| Win-prob log loss | {g['win_prob_log_loss']:.4f} | below {MODEL_ONLY_BAR:.4f} | {g['beats_model_only_0_6344']} |",
        f"| ECE (10 equal-count bins) | {g['ece']:.4f} | below 0.020 | {g['ece_ok']} |",
        f"| Top bin p>=0.80 absolute error | {top['abs_error']:.4f} (n={top['n']}) | below 0.03 | {g['top_bin_ok']} |",
        "",
        f"On the same {payload['n_decided']} games the model-only log loss is {wp['model_only']['log_loss']:.4f} "
        f"and the de-vigged close is {wp['market']['log_loss']:.4f}. "
        f"Simulator minus model-only log loss is {diff['diff']:+.4f} "
        f"[{diff['ci'][0]:+.4f}, {diff['ci'][1]:+.4f}] "
        f"({BOOT_N} paired resamples, seed {BOOT_SEED}). Negative would mean the simulator is better.",
        "",
        "## Shape and distance to the real margins",
        "",
        f"Simulated total {sh['total_mean']:.2f} against actual {sh['actual_total_mean']:.2f}. "
        f"Simulated home margin {sh['home_margin']:.2f} against actual {sh['actual_home_margin']:.2f}. "
        f"Actual margin SD {sh['actual_margin_sd']:.2f}. "
        f"Actual share of 3 / 7 / 10: {sh['actual_keys']['3']:.3f} / {sh['actual_keys']['7']:.3f} / {sh['actual_keys']['10']:.3f}.",
        "",
        "Wasserstein-1 between the pooled simulated outcomes and the actual games "
        "(lower is closer). The current possession simulator is fed the Kalman total and the "
        "model-only margin.",
        "",
        "| Distribution | This simulator | Current possession simulator |",
        "|---|---|---|",
        f"| Margin | {w['margin']['hybrid']:.3f} | {w['margin']['current_drive']:.3f} |",
        f"| Total | {w['total']['hybrid']:.3f} | {w['total']['current_drive']:.3f} |",
        "",
        f"Over/under uses {ov['n']} games that did not land on the total. "
        "The linear model is a walk-forward logistic regression of the over on the closing total alone.",
        "",
        "## Calibration deciles",
        "",
        "| Bin | n | Predicted | Actual |",
        "|---|---|---|---|",
    ]
    for row in payload["calibration"]["deciles"]:
        lines.append(f"| {row['bin']} | {row['n']} | {row['pred']:.3f} | {row['actual']:.3f} |")
    lines += [
        "",
        f"Top bin is every prediction at or above 0.80, not the tenth decile: "
        f"predicted {top['pred']:.3f}, actual {top['actual']:.3f}, n={top['n']}.",
        "",
        "## Not in production",
        "",
        "`ensemblitz predict` is unchanged. No site template, stylesheet or string was edited. "
        "Neutral site turns off the only site effect, the home touchdown shift. "
        "There is no travel, altitude or weather input.",
        "",
    ]
    return "\n".join(lines)


def write_reports(payload: dict) -> None:
    C.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(finite(payload), indent=1) + "\n")
    REPORT_MD.write_text(render(payload))


def run_evaluation(n_sims: int = 2000, seed: int = 202603) -> dict:
    payload = evaluate(n_sims=n_sims, seed=seed)
    write_reports(payload)
    return payload
