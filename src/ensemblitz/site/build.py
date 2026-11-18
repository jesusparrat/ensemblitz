"""Render predictions/, results/ and reports/ into a static, bilingual site.

Spanish pages live at the site root, English pages under ``en/``. The data layer
(``_game``, ``_history``) is language independent; text is produced per language through
``i18n.Lang`` and the string tables in ``strings.py``.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from ensemblitz import config as C
from ensemblitz import news as N
from ensemblitz.data.stadiums import HOME_STADIUMS, haversine_km
from ensemblitz.sim import SimParams, simulate_games
from ensemblitz.site import charts
from ensemblitz.site.i18n import LANGS, Lang
from ensemblitz.site.names import full

HERE = Path(__file__).parent
REPO_URL = "https://github.com/jesusparrat/ensemblitz"
FLAG_PP = 5  # whole points between our number and the market that raise a flag
HFA = 1.8  # home-field advantage in points (Kalman hyper-parameter, see reports/backtest.json)
ROUTES = {
    "es": {
        "home": "index.html",
        "week": "jornada/{}.html",
        "game": "partido/{}.html",
        "history": "historial.html",
        "method": "metodo.html",
    },
    "en": {
        "home": "en/index.html",
        "week": "en/week/{}.html",
        "game": "en/game/{}.html",
        "history": "en/history.html",
        "method": "en/method.html",
    },
}
MODEL_KEYS = ["market", "elo", "kf", "lgbm", "lgbm_mkt", "sim", "ens"]


# ---------------------------------------------------------------- number helpers
def shown_pct(x: float) -> int:
    """The whole percentage the page prints for a probability."""
    return int(f"{x * 100:.0f}")


def gap_pts(a: float | None, b: float | None) -> int | None:
    """Difference in whole points computed from the two numbers the reader sees.

    66 % and 67 % give +1, never a rounded raw difference that could disagree with them.
    """
    return None if a is None or b is None else shown_pct(a) - shown_pct(b)


# ---------------------------------------------------------------- data
def _read(path: Path) -> dict | list | None:
    return json.loads(path.read_text()) if path.exists() else None


def load_inputs(root: Path) -> dict:
    preds = {}
    for p in sorted((root / "predictions").glob("*/week*.json")):
        d = json.loads(p.read_text())
        preds[(d["season"], d["week"])] = d
    odds = {}
    for p in sorted((root / "reports" / "odds").glob("*_week*.json")):
        d = json.loads(p.read_text())
        odds[(d["season"], d["week"])] = d
    graded = []
    for p in sorted((root / "results").glob("*/week*.json")):
        graded += json.loads(p.read_text())
    return {
        "preds": preds,
        "odds": odds,
        "graded": graded,
        "backtest": _read(root / "reports" / "backtest.json"),
        "baseline": _read(root / "reports" / "baseline_2018_2025.json"),
    }


def _why(g: dict, home: str, away: str, pick_home: bool, margin: float) -> dict:
    """The single biggest reason for the pick, chosen by rule from the game's inputs.

    This is a description of the inputs, not a decomposition of the model: the order is a
    quarterback change, a clear rest edge for the favourite, a long trip against a home favourite,
    wind, then home field for close games and team strength for the rest.
    """
    c = g["context"]
    fav, dog = (home, away) if pick_home else (away, home)
    changed = [t for t, k in ((home, "home_qb_change"), (away, "away_qb_change")) if c[k]]
    if changed:
        return {"key": "why_qb", "team": changed[0], "other": dog if changed[0] == fav else fav}
    fr, dr = (c["home_rest"], c["away_rest"]) if pick_home else (c["away_rest"], c["home_rest"])
    if fr - dr >= 3:
        return {"key": "why_rest", "team": fav, "n": fr, "m": dr}
    km = haversine_km(*HOME_STADIUMS[away], *HOME_STADIUMS[home])
    if pick_home and km >= 3000:
        return {"key": "why_trip", "team": dog, "km": km, "home": home}
    if not c["dome"] and c.get("weather_known") and (c["wind"] or 0) * 1.609 >= 30:
        return {"key": "why_wind", "wind": c["wind"]}
    if pick_home and margin <= 2 * HFA:
        return {"key": "why_home", "team": home}
    if not pick_home and margin < 3:
        return {"key": "why_away_close", "team": away}
    return {"key": "why_form", "team": fav, "other": dog}


def _facts(g: dict) -> list[dict]:
    """Structured context lines for the game page: rest, travel, quarterback, venue."""
    c = g["context"]
    home, away = g["home_team"], g["away_team"]
    km = haversine_km(*HOME_STADIUMS[away], *HOME_STADIUMS[home])
    chg = [t for t, k in ((home, "home_qb_change"), (away, "away_qb_change")) if c[k]]
    if c["dome"]:
        venue = {"v": "dome"}
    elif c.get("weather_known"):
        venue = {"v": "open", "temp": c["temp"], "wind": c["wind"]}
    else:
        venue = {"v": "open_nowx"}
    return [
        {"k": "rest", "home": home, "away": away, "h": c["home_rest"], "a": c["away_rest"]},
        {"k": "trip", "away": away, "km": km},
        {"k": "qb", "teams": chg},
        {"k": "venue", **venue},
    ]


def _game(
    g: dict,
    odds_game: dict | None,
    result: dict | None,
    news_items: list[dict] | None = None,
) -> dict:
    """Language independent view of one game; the headline is the model on its own."""
    home, away = g["home_team"], g["away_team"]
    probs = g["home_win_prob"]
    mo = g.get("model_only")
    legacy = mo is None  # frozen before web v2: its headline was the blended ensemble
    if legacy:
        ph, margin, total = probs["ensemble"], g["predicted_margin"], g["predicted_total"]
        sim, example = None, g["most_likely_score"]
    else:
        ph, margin, total = mo["home_win_prob"], mo["margin"], mo["total"]
        sim, example = mo["sim"], mo["example_score"]
    hp, ap = round((total + margin) / 2, 1), round((total - margin) / 2, 1)
    margin_d, total_d = round(hp - ap, 1), round(hp + ap, 1)
    pick_home = ph >= 0.5
    fav = home if pick_home else away
    p_win = ph if pick_home else 1 - ph
    agree = (margin_d > 0) == pick_home and abs(margin_d) >= 0.05
    if odds_game:
        mkt_home, mkt_n = odds_game["consensus_home_prob_shin"], odds_game["n_books"]
    else:
        mkt_home, mkt_n = probs.get("market"), 0
    mkt_win = None if mkt_home is None else (mkt_home if pick_home else 1 - mkt_home)
    diff = gap_pts(p_win, mkt_win)
    ens = probs["ensemble"] if pick_home else 1 - probs["ensemble"]
    rng = None
    if sim:
        rng = {
            "home": (sim["home_q10"], sim["home_q90"]),
            "away": (sim["away_q10"], sim["away_q90"]),
            "margin": (sim["margin_q10"], sim["margin_q90"]),
            "total": (sim["total_q10"], sim["total_q90"]),
        }
    final = None
    if result:
        tot, mar = result["total"], result["result"]
        final = {
            "home": int(round((tot + mar) / 2)),
            "away": int(round((tot - mar) / 2)),
            "ok": bool(result.get("headline_correct", result.get("ensemble_correct"))),
        }
    comps = {k: probs.get(k) for k in ("market", "elo", "kf", "lgbm", "lgbm_mkt")}
    comps["ensemble_model_only"] = probs.get("ensemble_model_only")
    comps["ensemble"] = probs["ensemble"]

    def side(p: float | None) -> float | None:
        return None if p is None else (p if pick_home else 1 - p)

    ab = g.get("absences") or {"home": [], "away": []}
    return {
        "id": g["game_id"],
        "home": home,
        "away": away,
        "home_name": full(home),
        "away_name": full(away),
        "kick_utc": g["kickoff_utc"],
        "legacy": legacy,
        "fav": fav,
        "pick_home": pick_home,
        "p_win": p_win,
        "pts_home": hp,
        "pts_away": ap,
        "margin": margin_d,
        "margin_ok": agree,
        "total": total_d,
        "range": rng,
        "mkt_win": mkt_win,
        "mkt_n": mkt_n,
        "diff": diff,
        "flag": diff is not None and abs(diff) >= FLAG_PP,
        "ens_win": ens,
        "comps": {k: side(v) for k, v in comps.items()},
        "market": g["market"],
        "why": _why(g, home, away, pick_home, abs(margin_d)),
        "facts": _facts(g),
        "absences": [
            {**a, "team": team}
            for team, key in ((home, "home"), (away, "away"))
            for a in ab.get(key, [])
        ],
        "example": example,
        "saved_at": g["generated_at"],
        "final": final,
        "news": [x for x in (news_items or []) if x["team"] in (home, away)],
    }


def game_charts(g: dict, L: Lang) -> dict[str, str]:
    """Margin and total distributions from a fresh deterministic simulation of the shown means."""
    h, a = simulate_games(
        np.array([g["pts_home"]]),
        np.array([g["pts_away"]]),
        n_sims=20000,
        seed=11,
        params=SimParams(),
    )
    margin, total = (h - a)[0], (h + a)[0]
    side = "home" if g["pick_home"] else "away"
    spread, tl = g["market"]["spread_line"], g["market"]["total_line"]
    m_chart = charts.histogram(
        margin,
        -35,
        35,
        side,
        spread,
        L.text("chart.line", v=L.signed(spread)) if spread is not None else "",
        L.text("chart.wins", team=g["away"]),
        L.text("chart.wins", team=g["home"]),
        L.text("chart.margin_aria"),
    )
    t_chart = charts.histogram(
        total,
        10,
        80,
        None,
        tl,
        L.text("chart.line", v=L.n(tl)) if tl is not None else "",
        "",
        L.text("chart.points"),
        L.text("chart.total_aria"),
        split=None,
    )
    return {"margin": m_chart, "total": t_chart}


# ---------------------------------------------------------------- history
def _history(inputs: dict) -> dict:
    """Graded picks, each against the number that was the headline when it was saved."""
    by_id = {g["game_id"]: g for d in inputs["preds"].values() for g in d["games"]}
    rows = sorted(
        (r for r in inputs["graded"] if r["game_id"] in by_id and r["result"] != 0),
        key=lambda r: by_id[r["game_id"]]["kickoff_utc"],
    )
    out = []
    series = {"official": [], "market": []}
    ok_n = mk_n = 0
    sources = {"official": [0, 0], "model_only": [0, 0], "market": [0, 0], "ensemble": [0, 0]}
    for r in rows:
        p = by_id[r["game_id"]]
        headline = r.get("headline") or p.get("headline", "ensemble")
        ok = r.get("headline_correct", r.get("ensemble_correct"))
        if ok is None:
            continue
        mo = p.get("model_only")
        ph = (
            mo["home_win_prob"]
            if (headline == "model_only" and mo)
            else p["home_win_prob"]["ensemble"]
        )
        out.append(
            {
                **r,
                "headline": headline,
                "p": ph if r["pick"] == r["home_team"] else 1 - ph,
                "ok": bool(ok),
                "saved_at": p["generated_at"],
                "kick_utc": p["kickoff_utc"],
                "home_pts": int(round((r["total"] + r["result"]) / 2)),
                "away_pts": int(round((r["total"] - r["result"]) / 2)),
            }
        )
        n = len(out)
        ok_n += int(ok)
        series["official"].append(ok_n / n)
        sources["official"][0] += int(ok)
        sources["official"][1] += 1
        for key, comp in (
            ("model_only", "ensemble_model_only"),
            ("market", "market"),
            ("ensemble", "ensemble"),
        ):
            v = r.get(f"{comp}_correct")
            if v is not None:
                sources[key][0] += int(v)
                sources[key][1] += 1
        mv = r.get("market_correct")
        if mv is not None:
            mk_n += int(mv)
        series["market"].append(mk_n / n)
    weeks: dict[tuple, dict] = {}
    for r in out:
        w = weeks.setdefault(
            (r["season"], r["week"]), {"season": r["season"], "week": r["week"], "n": 0, "ok": 0}
        )
        w["n"] += 1
        w["ok"] += int(r["ok"])
    saved = [
        {
            "season": k[0],
            "week": k[1],
            "saved_at": d["generated_at"],
            "n": len(d["games"]),
            "first_kick": min(g["kickoff_utc"] for g in d["games"]),
            "headline": d["games"][0].get("headline", "ensemble") if d["games"] else "ensemble",
        }
        for k, d in sorted(inputs["preds"].items(), reverse=True)
    ]
    return {
        "rows": out,
        "sources": {k: {"ok": v[0], "n": v[1]} for k, v in sources.items()},
        "series": series,
        "weeks": list(weeks.values()),
        "saved": saved,
    }


# ---------------------------------------------------------------- build
class Site:
    """One build: renders every page in every language."""

    def __init__(self, root: Path, out: Path) -> None:
        self.root, self.out = root, out
        self.inputs = load_inputs(root)
        self.env = Environment(
            loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"])
        )
        self.now = datetime.now(UTC)

    def render(self, L: Lang, tpl: str, kind: str, key: object = None, **ctx: object) -> None:
        dest = ROUTES[L.code][kind].format(key)
        rel = "../" * dest.count("/")

        def u(k: str, kk: object = None) -> str:
            return rel + ROUTES[L.code][k].format(kk)

        alt = {
            c: rel + ROUTES[c][kind].format(key)
            for c in LANGS  # the same page in each language, for the switch and hreflang
        }
        text = self.env.get_template(tpl).render(
            L=L,
            lang=L.code,
            t=L.t,
            tx=L.text,
            n=L.n,
            signed=L.signed,
            pct=L.pct,
            pct_int=L.pct_int,
            rng=L.rng,
            fav_txt=L.fav,
            stamp=L.stamp,
            full=full,
            shown=shown_pct,
            why_text=lambda g: why_text(L, g),
            absence_list=lambda g: absence_list(L, g),
            news_status=lambda s: L.text(f"status_{s}"),
            u=u,
            rel=rel,
            alt=alt,
            other=next(c for c in LANGS if c != L.code),
            page_kind=kind,
            generated_at=L.stamp(self.now.strftime("%Y-%m-%dT%H:%M:%SZ")),
            repo=REPO_URL,
            flag_pts=FLAG_PP,
            weeks=sorted(self.inputs["preds"]),
            **ctx,
        )
        path = self.out / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def build(self) -> Path:
        out, inputs = self.out, self.inputs
        if out.exists():
            shutil.rmtree(out)
        (out / "assets").mkdir(parents=True)
        shutil.copytree(HERE / "static", out / "assets", dirs_exist_ok=True)
        news_by_week = {k: N.load_news(N.news_path(*k, root=self.root)) for k in inputs["preds"]}
        week_pages: dict[tuple, list[dict]] = {}
        for key, d in inputs["preds"].items():
            og = {x["game_id"]: x for x in (inputs["odds"].get(key) or {}).get("games", [])}
            graded = {r["game_id"]: r for r in inputs["graded"]}
            week_pages[key] = sorted(
                (
                    _game(g, og.get(g["game_id"]), graded.get(g["game_id"]), news_by_week[key])
                    for g in d["games"]
                ),
                key=lambda x: x["kick_utc"],
            )
        current = _current_week(week_pages, self.now)
        hist = _history(inputs)
        for code in LANGS:
            L = Lang(code)
            self._pages(L, week_pages, news_by_week, current, hist)
        (out / ".nojekyll").write_text("")
        return out

    def _pages(
        self, L: Lang, week_pages: dict, news_by_week: dict, current: tuple | None, hist: dict
    ) -> None:
        inputs = self.inputs
        for key, games in week_pages.items():
            for g in games:
                g["kick"] = L.kick(g["kick_utc"])
            pred = inputs["preds"][key]
            flagged = [g for g in games if g["flag"]]
            ctx = {
                "season": key[0],
                "week": key[1],
                "games": games,
                "meta": pred,
                "has_market_books": any(g["mkt_n"] for g in games),
                "flagged": flagged,
                "days": _days(games, L),
                "strip": news_by_week[key],
                "nxt": _next_game(games, self.now),
                "graded": [g for g in games if g["final"]],
                "is_current": key == current,
                "legacy": any(g["legacy"] for g in games),
            }
            self.render(L, "week.html", "week", key[1], **ctx)
            if key == current:
                self.render(L, "week.html", "home", None, **ctx)
            for g in games:
                self.render(
                    L,
                    "game.html",
                    "game",
                    g["id"],
                    g=g,
                    charts=game_charts(g, L),
                    season=key[0],
                    week=key[1],
                    facts=[fact_text(L, f) for f in g["facts"]],
                )
        if current is None:
            self.render(L, "empty.html", "home")
        hist_ctx = {
            "hist": hist,
            "chart": charts.running_lines(
                {
                    L.text("hist.series_official"): hist["series"]["official"],
                    L.text("hist.series_market"): hist["series"]["market"],
                },
                L.text("hist.chart_aria"),
            )
            if len(hist["rows"]) >= 2
            else "",
            "kick": lambda s: L.kick(s),
        }
        self.render(L, "history.html", "history", **hist_ctx)
        bt, bl = inputs["backtest"], inputs["baseline"]
        self.render(
            L,
            "method.html",
            "method",
            bt=bt,
            bl=bl,
            model_labels={k: L.text(f"model_{k}") for k in MODEL_KEYS},
            calib=charts.calibration(
                bt["calibration"]["ens"],
                L.text("calib.x"),
                L.text("calib.y"),
                L.text("calib.aria"),
            )
            if bt
            else "",
        )


def build_site(root: Path | None = None, out: Path | None = None) -> Path:
    root = root or C.ROOT
    return Site(root, out or root / "site" / "_build").build()


def why_text(L: Lang, g: dict) -> Markup:
    """One plain sentence for the biggest reason, in the reader's language."""
    w = dict(g["why"])
    key = w.pop("key")
    if key == "why_trip":
        w["km"] = L.n(w["km"], 0)
    if key == "why_wind":
        w["wind"] = L.kmh(w["wind"])
    return L.t(key, **w)


def absence_list(L: Lang, g: dict) -> str:
    """'Danielle Hunter (HOU, out, 1.8 pts)' for each notable absence, as plain context."""
    return ", ".join(
        L.text(
            "card.absence_item",
            player=a["player"],
            team=a["team"],
            status=L.text(f"status_{a['status']}").lower(),
            pts=L.n(a["points"], 1),
        )
        for a in g["absences"]
    )


def fact_text(L: Lang, f: dict) -> tuple[str, str]:
    """(label, value) for one context line."""
    k = f["k"]
    if k == "rest":
        v = L.text("fact.rest_v", home=f["home"], h=f["h"], away=f["away"], a=f["a"])
        return L.text("fact.rest"), v
    if k == "trip":
        return L.text("fact.trip"), L.text("fact.trip_v", away=f["away"], km=L.n(f["km"], 0))
    if k == "qb":
        teams = " / ".join(f["teams"])
        v = L.text("fact.qb_change", teams=teams) if f["teams"] else L.text("fact.qb_same")
        return L.text("fact.qb"), v
    if f["v"] == "open":
        v = L.text("fact.venue_open", temp=L.temp_c(f["temp"]), wind=L.kmh(f["wind"]))
    else:
        v = L.text("fact.venue_" + f["v"])
    return L.text("fact.venue"), v


def _days(games: list[dict], L: Lang) -> list[dict]:
    """Group games by Madrid calendar day (a Sunday-night game belongs to Monday there)."""
    days: dict[str, dict] = {}
    for g in games:
        d = days.setdefault(
            g["kick"]["date"],
            {"key": g["kick"]["date"], "label": g["kick"]["day_full"], "games": []},
        )
        d["games"].append(g)
    for d in days.values():
        n = len(d["games"])
        sub = L.text("day.games_one" if n == 1 else "day.games_n", n=n)
        night = d["games"][0]["kick"]["us_night"]
        if n == 1 and night:
            sub += ", " + L.text("day.night", night=night)
        d["sub"] = sub
        d["id"] = "d" + d["key"].replace("-", "")
    return list(days.values())


def _next_game(games: list[dict], now: datetime) -> dict | None:
    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    up = [g for g in games if g["kick_utc"] > iso]
    return up[0] if up else None


def _current_week(week_pages: dict[tuple, list[dict]], now: datetime) -> tuple | None:
    if not week_pages:
        return None
    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    upcoming = [k for k, gs in sorted(week_pages.items()) if any(g["kick_utc"] > iso for g in gs)]
    return upcoming[0] if upcoming else max(week_pages)
