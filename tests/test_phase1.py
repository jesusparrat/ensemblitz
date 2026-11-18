"""Phase 1: injury impact, availability and the margin table never use the week they predict."""

import numpy as np
import pandas as pd
import pytest
from scipy.special import ndtr

from ensemblitz import baseline as B
from ensemblitz import impact as I  # noqa: E741
from ensemblitz import margin as MG
from ensemblitz import phase1 as P
from test_baseline import _frame

TEAMS = ["AAA", "BBB", "CCC", "DDD"]
POS = {"QB": "QB", "RB": "RB", "WR": "WR", "OL": "OL", "EDGE": "DE", "CB": "CB"}


def _pg(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    pid = 0
    for team in TEAMS:
        for grp in POS:
            for _ in range(3 if grp in ("QB", "RB", "WR") else 4):
                pid += 1
                for season in (2016, 2017, 2018):
                    for week in range(1, 19):
                        starter = pid % 3 != 0
                        r = {"gsis": f"P{pid}", "season": season, "week": week, "group": grp}
                        r.update({c: 0.0 for c in I.STAT_COLS})
                        if grp == "QB":
                            r["attempts"] = float(rng.integers(20, 40)) * starter
                            r["passing_epa"] = r["attempts"] * rng.normal(0.05, 0.2)
                        elif grp in ("RB", "WR"):
                            r["targets"] = float(rng.integers(0, 9)) * starter
                            r["receiving_epa"] = r["targets"] * rng.normal(0.0, 0.3)
                        else:
                            r["def_sacks"] = float(rng.integers(0, 2))
                        r["off_pct"] = 0.9 * starter if grp in ("QB", "RB", "WR", "OL") else 0.0
                        r["def_pct"] = 0.8 * starter if grp in ("EDGE", "CB") else 0.0
                        r["played"] = float(starter)
                        r["tau"] = float(I.tau(season, week))
                        r["team"] = team
                        rows.append(r)
    return pd.DataFrame(rows)


def _injury_rows(pg: pd.DataFrame, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for r in pg.itertuples(index=False):
        if rng.uniform() < 0.12:
            rows.append(
                {
                    "season": r.season,
                    "week": r.week,
                    "team": r.team,
                    "gsis_id": r.gsis,
                    "group": r.group,
                    "label": rng.choice(["Out", "Doubtful", "Questionable"]),
                    "practice": rng.choice(["full", "limited", "dnp"]),
                    "listed": True,
                    "snaps_known": True,
                    "played": float(rng.uniform() < 0.5),
                    "tau": float(I.tau(r.season, r.week)),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def pg():
    return _pg()


@pytest.fixture(scope="module")
def rows(pg):
    return _injury_rows(pg)


def test_player_value_ignores_current_and_future_weeks(pg):
    t0 = int(I.tau(2018, 8))
    base = I.value_table(pg, t0)
    bad = pg.copy()
    m = bad["tau"] >= t0
    rng = np.random.default_rng(5)
    for c in I.STAT_COLS:
        bad.loc[m, c] = rng.uniform(0, 500, int(m.sum()))
    bad.loc[m, ["off_pct", "def_pct"]] = 1.0
    again = I.value_table(bad, t0)
    pd.testing.assert_frame_equal(base.sort_index(), again.sort_index())
    older = pg.copy()
    older.loc[older["tau"] < t0 - 10, "passing_epa"] += 50.0
    assert not np.allclose(I.value_table(older, t0)["value_pts"], base["value_pts"])


def test_values_are_nonnegative_and_capped(pg):
    vt = I.value_table(pg, int(I.tau(2018, 12)))
    assert (vt["value_pts"] >= 0).all()
    for g, cap in I.CAPS.items():
        assert np.nanmax(np.r_[0.0, vt.loc[vt["group"] == g, "value_pts"].to_numpy()]) <= cap + 1e-9


def test_availability_uses_only_earlier_weeks(rows):
    t0 = int(I.tau(2018, 8))
    base = I.Availability(rows, t0)
    bad = rows.copy()
    m = bad["tau"] >= t0
    bad.loc[m, "played"] = 1.0 - bad.loc[m, "played"]
    bad.loc[m, "label"] = "Probable"
    again = I.Availability(bad, t0)
    for a in [("Out", "dnp", "QB"), ("Questionable", "full", "WR"), ("Doubtful", "limited", "OL")]:
        assert base.p_play(*a) == again.p_play(*a)
        assert 0.0 <= base.p_play(*a) <= 1.0


def test_availability_learns_the_label():
    rng = np.random.default_rng(2)
    n = 3000
    lab = rng.choice(["Out", "Questionable"], n)
    played = np.where(lab == "Out", 0.0, (rng.uniform(size=n) < 0.7).astype(float))
    rows = pd.DataFrame(
        {
            "label": lab,
            "practice": "limited",
            "group": "WR",
            "listed": True,
            "snaps_known": True,
            "played": played,
            "tau": np.arange(n, dtype=float),
        }
    )
    av = I.Availability(rows, tau0=n + 1)
    assert av.p_play("Out", "limited", "WR") < 0.02
    assert abs(av.p_play("Questionable", "limited", "WR") - 0.7) < 0.05


def test_injury_features_ignore_the_week_they_describe(pg, rows):
    games = pd.DataFrame(
        {
            "game_id": ["2018_09_BBB_AAA", "2018_09_DDD_CCC"],
            "season": 2018,
            "week": 9,
            "home_team": ["AAA", "CCC"],
            "away_team": ["BBB", "DDD"],
        }
    )
    kw = dict(first_season=2018, last_season=2018)
    base = I.injury_features(games, pg, rows, **kw)
    t0 = int(I.tau(2018, 9))
    bad_rows, bad_pg = rows.copy(), pg.copy()
    m = bad_rows["tau"] >= t0
    bad_rows.loc[m, "played"] = 1.0 - bad_rows.loc[m, "played"]  # outcomes are never an input
    mp = bad_pg["tau"] >= t0
    bad_pg.loc[mp, "passing_epa"] = 9999.0
    bad_pg.loc[mp, "attempts"] = 5.0
    again = I.injury_features(games, bad_pg, bad_rows, **kw)
    pd.testing.assert_frame_equal(base, again)
    assert (base.drop(columns="game_id") >= 0).all().all()


def test_margin_probabilities_are_valid_symmetric_and_monotone():
    rng = np.random.default_rng(0)
    spread = rng.normal(0, 6, 4000)
    result = np.round(spread + rng.normal(0, 13, 4000))
    mdl = MG.fit(spread, result)
    m = np.linspace(-20, 20, 81)
    p = mdl.prob_home(m)
    assert ((p > 0) & (p < 1)).all()
    assert np.allclose(p, 1 - mdl.prob_home(-m), atol=1e-9)
    assert (np.diff(p) > 0).all()
    assert abs(mdl.prob_home(np.array([0.0]))[0] - 0.5) < 1e-9


def test_margin_table_learns_the_key_number():
    rng = np.random.default_rng(1)
    spread = rng.normal(0, 6, 8000)
    result = np.round(spread + rng.normal(0, 13, 8000))
    # push a third of the games that end 1 to 5 points from a field goal onto exactly 3
    near = (np.abs(result) >= 1) & (np.abs(result) <= 5) & (rng.uniform(size=8000) < 0.35)
    result = np.where(near, 3 * np.sign(result), result)
    mdl = MG.fit(spread, result)
    assert mdl.w[3] > 1.4 and mdl.w[3] > mdl.w[2] and mdl.w[3] > mdl.w[4]
    # with a flat table the probability is the normal curve
    flat = MG.MarginModel(np.ones(MG.K + 1), 13.4)
    assert np.allclose(flat.prob_home(np.array([4.0])), ndtr(4.0 / 13.4), atol=0.01)


def test_margin_fit_uses_only_earlier_games():
    rng = np.random.default_rng(3)
    rows = []
    for season in range(2000, 2012):
        for week in range(1, 18):
            s = rng.normal(0, 6, 10)
            rows.append(
                pd.DataFrame(
                    {
                        "season": season,
                        "week": week,
                        "spread_line": s,
                        "result": np.round(s + rng.normal(0, 13, 10)),
                    }
                )
            )
    h = pd.concat(rows, ignore_index=True)
    base = MG.fit_before(h, 2008, 9)
    bad = h.copy()
    fut = (bad["season"] > 2008) | ((bad["season"] == 2008) & (bad["week"] >= 9))
    bad.loc[fut, "result"] = 3.0
    again = MG.fit_before(bad, 2008, 9)
    assert np.array_equal(base.w, again.w) and base.sigma == again.sigma


def test_fit_betas_shrinks_to_prior_and_recovers_signal():
    k = 5
    b0 = P.fit_betas(np.zeros((0, k)), np.zeros(0))
    assert np.allclose(b0, P.PRIOR_BETA)
    rng = np.random.default_rng(4)
    d = rng.normal(0, 1, (60000, k))
    truth = np.array([0.9, 0.2, 0.0, 0.5, 0.7])
    resid = -(d @ truth) + rng.normal(0, 13, 60000)
    b = P.fit_betas(d, resid)
    assert np.all(np.abs(b - truth) < 0.15)
    assert (b >= 0).all()


def _synthetic_p1(seed: int = 0):
    frame = _frame(seed)
    wf, _ = B.walk_forward(frame, first=2017)
    rng = np.random.default_rng(seed + 9)
    feats = pd.DataFrame({"game_id": frame["game_id"]})
    for side in ("h", "a"):
        for t in ("", "b"):
            for g in P.GROUPS:
                feats[f"{side}{t}_{g}"] = rng.gamma(1.0, 0.5, len(frame))
    hist_rows = []
    for season in range(1999, 2020):
        for week in range(1, 19):
            s = rng.normal(0, 6, 8)
            hist_rows.append(
                pd.DataFrame(
                    {
                        "season": season,
                        "week": week,
                        "spread_line": s,
                        "result": np.round(s + rng.normal(0, 13, 8)),
                    }
                )
            )
    return wf, feats, pd.concat(hist_rows, ignore_index=True)


def test_phase1_walk_forward_has_no_future_leakage():
    wf, feats, hist = _synthetic_p1()
    out, folds = P.walk_forward(wf, feats, hist)
    assert folds and out["D_inj"].between(0, 1).all() or out["D_inj"].dropna().between(0, 1).all()
    cut = (2018, 10)
    fut = (wf["season"] > cut[0]) | ((wf["season"] == cut[0]) & (wf["week"] >= cut[1]))
    bad = wf.copy()
    rng = np.random.default_rng(8)
    n = int(fut.sum())
    bad.loc[fut, "result"] = rng.normal(0, 30, n).round()
    bad.loc[fut, "model_only_margin"] = rng.normal(0, 8, n)
    bad_feats = feats.copy()
    fmask = bad_feats["game_id"].isin(wf.loc[fut, "game_id"])
    for c in bad_feats.columns[1:]:
        bad_feats.loc[fmask, c] = rng.gamma(2.0, 3.0, int(fmask.sum()))
    bad_hist = hist.copy()
    hf = (bad_hist["season"] > 2018) | ((bad_hist["season"] == 2018) & (bad_hist["week"] >= 10))
    bad_hist.loc[hf, "result"] = 7.0
    out2, _ = P.walk_forward(bad, bad_feats, bad_hist)
    before = ~out["game_id"].isin(wf.loc[fut, "game_id"])
    for c in ("inj_margin", "adj", "B_normal", "C_discrete", "D_inj", "D_total", "D_binary"):
        a = out.loc[before, c].to_numpy()
        b = out2.loc[out2["game_id"].isin(out.loc[before, "game_id"]), c].to_numpy()
        assert np.allclose(a, b, equal_nan=True), c
    # and the week itself: its own result never feeds its own prediction
    wk = (wf["season"] == 2019) & (wf["week"] == 4)
    own = wf.copy()
    own.loc[wk, "result"] = 99.0
    out3, _ = P.walk_forward(own, feats, hist)
    ids = wf.loc[wk, "game_id"]
    for c in ("inj_margin", "D_inj", "C_discrete"):
        assert np.allclose(
            out.loc[out["game_id"].isin(ids), c], out3.loc[out3["game_id"].isin(ids), c]
        ), c


def test_paired_bootstrap_detects_a_real_difference_and_not_a_null():
    rng = np.random.default_rng(6)
    p = rng.uniform(0.2, 0.8, 3000)
    y = (rng.uniform(size=3000) < p).astype(float)
    d = pd.DataFrame(
        {"good": p, "bad": np.clip(p + rng.normal(0, 0.15, 3000), 0.02, 0.98), "same": p}
    )
    out = P.paired(d, y, [("good", "bad"), ("good", "same")], n=500)
    assert out["good__minus__bad"]["ll"]["ci"][1] < 0
    assert out["good__minus__same"]["ll"]["diff"] == 0.0
