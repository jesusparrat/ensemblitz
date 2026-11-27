"""Structured, strictly separated model explanations and pre-game matchup diagnostics.

Design rules (PR 5, Option B):
- Never claim LightGBM TreeSHAP explains the complete ``model_only`` stack.
- Never proportionally redistribute SHAP values across Kalman components or merge
  attributions from distinct models into a single synthetic sum.
- Keep four audit layers mathematically exact and separate:
  1. ``stack``: exact ``model_only`` logit stack + NNLS margin blend over ``[elo, kf, lgbm]``.
  2. ``lgbm_shap``: exact LightGBM TreeSHAP feature-group attributions (margin points).
  3. ``kalman``: exact additive Kalman state-space margin decomposition.
  4. ``elo``: exact additive Elo margin decomposition (team gap + Elo HFA).
- ``matchups`` are purely descriptive pre-game comparisons of opponent-adjusted EPA/play
  and EPA allowed/play (``combined_epa = off_epa + def_epa_allowed``). They are NOT causal
  effects or predicted margin contributions.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.special import logit

from ensemblitz.features.build import HOME_ADV_ELO_PTS, feature_columns
from ensemblitz.models.ensemble import MODEL_COMPONENTS, PROB_EPS, StackModel

# Exact partition of feature_columns(include_market=False) into 6 semantic NFL groups.
LGBM_GROUPS: dict[str, tuple[str, ...]] = {
    "pass_game": ("h_vs_a_pass", "a_vs_h_pass", "net_pass"),
    "rush_game": ("h_vs_a_rush", "a_vs_h_rush", "net_rush"),
    "efficiency": ("h_vs_a_sr", "a_vs_h_sr", "net_sr"),
    "qb": (
        "h_qb_rate",
        "a_qb_rate",
        "qb_diff",
        "h_qb_exp",
        "a_qb_exp",
        "h_qb_change",
        "a_qb_change",
    ),
    "team_strength": ("elo_diff", "elo_prob", "kf_margin", "kf_total"),
    "situational": (
        "h_rest",
        "a_rest",
        "rest_diff",
        "h_bye",
        "a_bye",
        "a_travel_km",
        "a_tz_shift",
        "h_travel_km",
        "neutral",
        "div_game",
        "dome",
        "temp",
        "wind",
        "turf",
        "h_out_lag",
        "a_out_lag",
        "week",
    ),
}

# Verified historical performance for the fixed >= 10 pp site-printed discrepancy threshold
# over the 2,133 decided 2018-2025 regular-season baseline games (stratified 2-week block
# bootstrap, 10,000 reps, seed 20260, 72 blocks).
DISCREPANCY_10PP_HISTORY = {
    "threshold_pp": 10,
    "n_games": 506,
    "n_total": 2133,
    "share_pct": 23.7,
    "model_only_acc": 0.599,
    "model_only_acc_ci95": (0.561, 0.637),
    "market_acc": 0.658,
    "market_acc_ci95": (0.615, 0.702),
    "acc_diff_pp": -5.9,
    "acc_diff_ci95_pp": (-11.5, -0.4),
    "model_only_ll": 0.6732,
    "market_ll": 0.6069,
    "ll_diff_ci95": (0.0382, 0.0949),
    "opposite_winner_n": 192,
    "opposite_winner_model_acc": 0.422,
    "opposite_winner_market_acc": 0.578,
}


def _r(val: object, digits: int = 4) -> float:
    x = float(val)
    if not math.isfinite(x):
        raise ValueError(f"non-finite diagnostic value: {val!r}")
    return round(x, digits)


def _clipped_logit(p: float) -> float:
    return float(logit(np.clip(float(p), PROB_EPS, 1.0 - PROB_EPS)))


def stack_decomposition(row: pd.Series, model: StackModel) -> dict:
    """Exact ``model_only`` stack aggregation over its components (logit + NNLS margin)."""
    comps = list(model.comps)
    if comps != MODEL_COMPONENTS:
        raise ValueError(f"expected model_only components {MODEL_COMPONENTS}, got {comps}")
    logit_contribs = {
        c: _r(float(w) * _clipped_logit(float(row[f"{c}_prob"])), 4)
        for c, w in zip(comps, model.w, strict=True)
    }
    margin_contribs = {
        c: _r(float(mw) * float(row[f"{c}_margin"]), 3)
        for c, mw in zip(comps, model.margin_w, strict=True)
    }
    return {
        "components": comps,
        "prob_weights": [_r(w, 4) for w in model.w],
        "prob_bias": _r(model.b, 4),
        "logit_contributions": logit_contribs,
        "margin_weights": [_r(mw, 4) for mw in model.margin_w],
        "margin_contributions": margin_contribs,
    }


def lgbm_shap_decomposition(contrib_row: pd.Series, pred_margin: float) -> dict:
    """Group exact LightGBM TreeSHAP contributions into 6 semantic buckets (LightGBM only)."""
    expected_cols = set(feature_columns(include_market=False))
    grouped_cols = {c for cols in LGBM_GROUPS.values() for c in cols}
    if grouped_cols != expected_cols:
        raise ValueError("LGBM_GROUPS must partition feature_columns(include_market=False)")
    groups = {
        name: _r(sum(float(contrib_row[c]) for c in cols), 3) for name, cols in LGBM_GROUPS.items()
    }
    base_margin = _r(float(contrib_row["_base_margin"]), 3)
    return {
        "base_margin": base_margin,
        "pred_margin": _r(float(pred_margin), 3),
        "groups": groups,
    }


def kalman_decomposition(row: pd.Series) -> dict:
    """Exact additive Kalman margin decomposition (Kalman component only)."""
    hfa = float(row["kf_hfa"])
    h_off = float(row["kf_h_off"])
    a_def = float(row["kf_a_def"])
    a_off = float(row["kf_a_off"])
    h_def = float(row["kf_h_def"])
    return {
        "margin": _r(float(row["kf_margin"]), 3),
        "hfa": _r(hfa, 3),
        "home_off": _r(h_off, 3),
        "away_def_allowed": _r(a_def, 3),
        "away_off": _r(a_off, 3),
        "home_def_allowed": _r(h_def, 3),
        "home_off_vs_away_def": _r(h_off + a_def, 3),
        "away_off_vs_home_def": _r(a_off + h_def, 3),
    }


def elo_decomposition(row: pd.Series) -> dict:
    """Exact additive Elo margin decomposition (Elo component only)."""
    elo_h = float(row["elo_h"])
    elo_a = float(row["elo_a"])
    elo_margin = float(row["elo_margin"])
    team_margin = (elo_h - elo_a) / HOME_ADV_ELO_PTS
    hfa_margin = elo_margin - team_margin
    return {
        "margin": _r(elo_margin, 3),
        "team_margin": _r(team_margin, 3),
        "hfa_margin": _r(hfa_margin, 3),
        "home_rating": _r(elo_h, 1),
        "away_rating": _r(elo_a, 1),
    }


def unit_matchups(row: pd.Series) -> list[dict]:
    """Four descriptive pre-game unit-vs-unit opponent-adjusted EPA comparisons.

    In ``features/build.py``, offensive ratings are opponent-adjusted EPA gained per play
    (higher = better offense) and defensive ratings are opponent-adjusted EPA allowed per
    play (higher = worse defense, lower = better defense).

    The descriptive indicator ``combined_epa = off_epa + def_epa_allowed`` is positive
    when the matchup tilts toward the offense (good offense vs weak defense) and negative
    when it tilts toward the defense (weak offense vs strong defense). It is strictly a
    descriptive comparison, not a causal effect or predicted margin contribution.
    """
    home = str(row["home_team"])
    away = str(row["away_team"])
    specs = (
        ("home_pass", "pass", home, away, "h_off_pass", "a_def_pass"),
        ("away_pass", "pass", away, home, "a_off_pass", "h_def_pass"),
        ("home_rush", "rush", home, away, "h_off_rush", "a_def_rush"),
        ("away_rush", "rush", away, home, "a_off_rush", "h_def_rush"),
    )
    items: list[dict] = []
    for mid, unit, off_t, def_t, off_col, def_col in specs:
        off_epa = float(row[off_col])
        def_epa = float(row[def_col])
        combined = off_epa + def_epa
        off_rank = int(row[f"{off_col}_rank"])
        def_rank = int(row[f"{def_col}_rank"])
        favors = off_t if combined >= 0.0 else def_t
        items.append(
            {
                "id": mid,
                "unit": unit,
                "off_team": off_t,
                "def_team": def_t,
                "off_epa": _r(off_epa, 3),
                "off_rank": off_rank,
                "def_epa_allowed": _r(def_epa, 3),
                "def_rank": def_rank,
                "combined_epa": _r(combined, 3),
                "favors": favors,
            }
        )
    # Sort descending by descriptive mismatch magnitude, deterministic tie-break by id.
    items.sort(key=lambda x: (-abs(x["combined_epa"]), x["id"]))
    return items


def qb_matchup_block(row: pd.Series) -> dict:
    """Pre-game decayed QB EPA per dropback (not opponent-adjusted) and starter change flags."""
    return {
        "home_epa_per_dropback": _r(float(row["h_qb_rate"]), 3),
        "away_epa_per_dropback": _r(float(row["a_qb_rate"]), 3),
        "diff_epa_per_dropback": _r(float(row["qb_diff"]), 3),
        "home_dropbacks": _r(float(row["h_qb_exp"]), 1),
        "away_dropbacks": _r(float(row["a_qb_exp"]), 1),
        "home_qb_change": bool(row["h_qb_change"]),
        "away_qb_change": bool(row["a_qb_change"]),
    }


def injury_context_block(absences: dict[str, list[dict]] | None, cutoff_utc: str) -> dict:
    """Serialized contextual injury diagnostics with point-in-time provenance."""
    ab = absences or {"home": [], "away": []}
    return {
        "source": "nflverse_injuries",
        "cutoff_utc": cutoff_utc,
        "included_in_model": False,
        "home": [dict(a) for a in ab.get("home", [])],
        "away": [dict(a) for a in ab.get("away", [])],
    }


def build_game_explanation(
    row: pd.Series,
    lgbm_contrib_row: pd.Series,
    no_market_stack: StackModel,
    absences: dict[str, list[dict]] | None,
    cutoff_utc: str,
) -> dict:
    """Assemble the complete contract-v1 ``explanation`` block for one game."""
    stack = stack_decomposition(row, no_market_stack)
    lgbm_shap = lgbm_shap_decomposition(lgbm_contrib_row, float(row["lgbm_margin"]))
    kf = kalman_decomposition(row)
    elo = elo_decomposition(row)
    matchups = unit_matchups(row)
    qb = qb_matchup_block(row)
    inj = injury_context_block(absences, cutoff_utc)

    pick_home = float(row["nomkt_prob"]) >= 0.5
    sign = 1.0 if pick_home else -1.0
    # Largest stack margin component supporting the picked side (fallback to largest magnitude).
    mc = stack["margin_contributions"]
    lead_comp = max(
        stack["components"],
        key=lambda c: (sign * mc[c], abs(mc[c]), c),
    )
    # Largest LightGBM TreeSHAP group supporting the picked side (strictly LightGBM).
    groups = lgbm_shap["groups"]
    lgbm_top_group = max(
        groups.keys(),
        key=lambda g: (sign * groups[g], abs(groups[g]), g),
    )
    qb_changes = []
    if qb["away_qb_change"]:
        qb_changes.append(str(row["away_team"]))
    if qb["home_qb_change"]:
        qb_changes.append(str(row["home_team"]))

    return {
        "season_week": int(row["week"]),
        "summary": {
            "lead_component": lead_comp,
            "lead_component_margin_home": mc[lead_comp],
            "top_matchup_id": matchups[0]["id"],
            "lgbm_top_group": lgbm_top_group,
            "lgbm_top_group_margin_home": groups[lgbm_top_group],
            "qb_change_teams": qb_changes,
        },
        "stack": stack,
        "lgbm_shap": lgbm_shap,
        "kalman": kf,
        "elo": elo,
        "matchups": matchups,
        "qb_matchup": qb,
        "injury_context": inj,
    }


__all__ = [
    "DISCREPANCY_10PP_HISTORY",
    "LGBM_GROUPS",
    "build_game_explanation",
    "elo_decomposition",
    "injury_context_block",
    "kalman_decomposition",
    "lgbm_shap_decomposition",
    "qb_matchup_block",
    "stack_decomposition",
    "unit_matchups",
]
