"""Audit of the nflverse injury reports for Phase 1 (needs network, not part of CI).

Questions answered:
1. Does each (season, week, player) row keep the Friday practice status, or is it overwritten
   by the final game-day inactives? (columns, timestamps, how often a player marked Out plays)
2. How likely is a player to actually play given the final report label and practice status?

"Played" = the player appears in the nflverse snap counts of that game with any snap.
Output: reports/injury_audit.json
"""

from __future__ import annotations

import json
from pathlib import Path

import nflreadpy as nfl
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "reports" / "injury_audit.json"
SEASONS = list(range(2015, 2026))


def main() -> None:
    inj = nfl.load_injuries(SEASONS).to_pandas()
    inj = inj[inj["game_type"] == "REG"].copy()
    snaps = nfl.load_snap_counts(SEASONS).to_pandas()
    players = nfl.load_players().to_pandas()[["gsis_id", "pfr_id"]].dropna()
    snaps = snaps[snaps["game_type"] == "REG"].merge(
        players, left_on="pfr_player_id", right_on="pfr_id", how="inner"
    )
    snaps["any_snap"] = (
        snaps[["offense_snaps", "defense_snaps", "st_snaps"]].fillna(0).sum(axis=1) > 0
    )
    played = snaps[snaps["any_snap"]][["season", "week", "gsis_id"]].drop_duplicates()
    played["played"] = True
    m = inj.merge(played, on=["season", "week", "gsis_id"], how="left")
    m["played"] = m["played"].fillna(False).astype(bool)
    # Only trust seasons/weeks where the snap table has data (a team on bye has no row anyway).
    ok_weeks = played.groupby(["season", "week"]).size().rename("n_played").reset_index()
    m = m.merge(ok_weeks, on=["season", "week"], how="inner")

    dm = inj["date_modified"].dropna().dt.tz_convert("America/New_York")
    ts = {
        "rows": int(len(inj)),
        "rows_per_player_week_duplicates": int(inj.duplicated(["season", "week", "gsis_id"]).sum()),
        "date_modified_present_by_season": {
            int(s): float(v)
            for s, v in inj["date_modified"].notna().groupby(inj["season"]).mean().items()
        },
        "date_modified_weekday_share": {
            k: float(v) for k, v in dm.dt.day_name().value_counts(normalize=True).round(4).items()
        },
    }
    by_report = (
        m.assign(report_status=m["report_status"].fillna("(sin etiqueta)"))
        .groupby("report_status")["played"]
        .agg(["size", "mean"])
    )
    by_practice = (
        m[m["report_status"].eq("Questionable")]
        .assign(practice_status=lambda d: d["practice_status"].fillna("(sin dato)"))
        .groupby("practice_status")["played"]
        .agg(["size", "mean"])
    )
    q = m[m["report_status"].eq("Questionable")]
    by_pos = q.groupby("position")["played"].agg(["size", "mean"])
    by_pos = by_pos[by_pos["size"] >= 100]
    by_season_q = q.groupby("season")["played"].mean()
    # How different are report_status and practice_status? (if the row were overwritten by the
    # final inactives, 'Out' rows would never show full practice participation)
    cross = pd.crosstab(
        m["report_status"].fillna("(sin etiqueta)"), m["practice_status"].fillna("(sin dato)")
    )

    def tab(t: pd.DataFrame) -> dict:
        return {
            str(k): {"n": int(r["size"]), "p_played": float(np.round(r["mean"], 4))}
            for k, r in t.iterrows()
        }

    res = {
        "source": "nflreadpy.load_injuries + load_snap_counts (temporada regular 2015-2025)",
        "timestamps": ts,
        "columns": inj.columns.tolist(),
        "p_played_by_report_status": tab(by_report),
        "p_played_questionable_by_practice_status": tab(by_practice),
        "p_played_questionable_by_position": tab(by_pos),
        "p_played_questionable_by_season": {
            int(k): float(np.round(v, 4)) for k, v in by_season_q.items()
        },
        "report_vs_practice_counts": {
            str(r): {str(c): int(v) for c, v in row.items()} for r, row in cross.iterrows()
        },
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False, allow_nan=False))
    print(json.dumps(res, indent=1, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
