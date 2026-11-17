"""Synthetic league used by the no-leakage tests (no network, runs in a second)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

TEAMS = ["BUF", "MIA", "NE", "NYJ", "KC", "LV", "LAC", "DEN"]


def make_league(seed: int = 0, seasons: int = 3, weeks: int = 6):
    rng = np.random.default_rng(seed)
    strength = dict(zip(TEAMS, rng.normal(0, 4, len(TEAMS)), strict=True))
    games, tg, qg = [], [], []
    gid = 0
    for s in range(2020, 2020 + seasons):
        for w in range(1, weeks + 1):
            order = rng.permutation(TEAMS)
            for i in range(0, len(order), 2):
                h, a = order[i], order[i + 1]
                gid += 1
                game_id = f"{s}_{w:02d}_{a}_{h}"
                margin = round(strength[h] - strength[a] + 2 + rng.normal(0, 13))
                hs = int(max(3, 22 + margin / 2 + rng.normal(0, 3)))
                as_ = int(max(0, hs - margin))
                games.append(
                    dict(
                        game_id=game_id,
                        season=s,
                        week=w,
                        kickoff_utc=pd.Timestamp(f"{s}-09-{w:02d}T17:00:00Z"),
                        home_team=h,
                        away_team=a,
                        played=True,
                        neutral=0,
                        div_game=0,
                        home_qb_id=f"qb_{h}",
                        away_qb_id=f"qb_{a}",
                        home_rest=7,
                        away_rest=7,
                        stadium_id=f"{h}00",
                        roof="outdoors",
                        temp=60.0,
                        wind=5.0,
                        surface="grass",
                        spread_line=float(round(strength[h] - strength[a] + 2)),
                        total_line=44.5,
                        home_moneyline=-150.0,
                        away_moneyline=130.0,
                        result=float(hs - as_),
                        total=float(hs + as_),
                        home_score=hs,
                        away_score=as_,
                    )
                )
                for t, sc in ((h, hs), (a, as_)):
                    tg.append(
                        dict(
                            game_id=game_id,
                            team=t,
                            n_pass=35,
                            n_rush=25,
                            epa_pass=float(rng.normal(0, 3) + (sc - 22) * 0.5),
                            epa_rush=float(rng.normal(0, 2)),
                            succ=float(rng.integers(20, 32)),
                        )
                    )
                    qg.append(
                        dict(
                            game_id=game_id,
                            qb_id=f"qb_{t}",
                            n_db=35,
                            epa_db=float(rng.normal(0, 3)),
                        )
                    )
    return pd.DataFrame(games), pd.DataFrame(tg), pd.DataFrame(qg)


@pytest.fixture(scope="session")
def league():
    return make_league()
