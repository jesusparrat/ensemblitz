"""Render predictions/, results/ and reports/ into a static site."""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ensemblitz import config as C
from ensemblitz import news as N
from ensemblitz.data.stadiums import HOME_STADIUMS, haversine_km
from ensemblitz.sim import SimParams, simulate_games
from ensemblitz.site import charts
from ensemblitz.site.names import book_name, full, nick

HERE = Path(__file__).parent
MADRID = ZoneInfo("Europe/Madrid")
REPO_URL = "https://github.com/jesusparrat/ensemblitz"
DAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
DAYS_FULL = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
US_NIGHT = {3: "jueves", 0: "lunes"}  # NFL standalone prime-time nights, US Eastern
EASTERN = ZoneInfo("America/New_York")
FLAG_PP = 0.05  # gap between the models alone and the bookmaker consensus that raises a flag
NA = "n/d"
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
COMP_LABELS = [
    ("elo", "Elo con margen de victoria"),
    ("kf", "Kalman (fuerza dinámica)"),
    ("lgbm", "LightGBM sin mercado"),
    ("lgbm_mkt", "LightGBM sobre el mercado"),
    ("market", "Mercado (cierre, sin comisión)"),
    ("sim", "Simulador de marcadores"),
    ("ensemble_model_only", "Ensemble solo modelos"),
    ("ensemble", "Ensemble (pick)"),
]
MODEL_LABELS = {
    "market": "Mercado (cierre)",
    "elo": "Elo (MOV)",
    "kf": "Kalman (fuerza dinámica)",
    "lgbm": "LightGBM (sin mercado)",
    "lgbm_mkt": "LightGBM (residuo vs mercado)",
    "sim": "Simulador (params Kalman)",
    "ens": "Ensemble",
}


STATUS_ES = {
    "out": "Baja",
    "doubtful": "Muy dudoso",
    "questionable": "Dudoso",
    "returning": "Vuelve",
    "other": "Novedad",
}


# ---------------------------------------------------------------- formatting helpers
def fnum(x: float | None, nd: int = 1) -> str:
    if x is None:
        return NA
    return f"{x:.{nd}f}".replace("-", "\u2212").replace(".", ",")


def fsigned(x: float | None, nd: int = 1) -> str:
    if x is None:
        return NA
    return ("+" if x > 0 else "") + fnum(x, nd)


def fpct(x: float | None, nd: int = 0) -> str:
    return NA if x is None else f"{fnum(x * 100, nd)}\u202f%"


def fpp(x: float | None) -> str:
    return NA if x is None else f"{fsigned(x * 100, 0 if abs(x) >= 0.095 else 1)}\u202fpp"


def fav(home: str, away: str, margin_home: float | None, nd: int = 1) -> str:
    """One margin convention everywhere: the favourite, minus the points it gives ('HOU \u221212,5')."""
    if margin_home is None:
        return NA
    if abs(margin_home) < 0.05:
        return "igualado"
    return f"{home if margin_home > 0 else away} \u2212{fnum(abs(margin_home), nd)}"


def c_temp(f: float | None) -> str:
    return NA if f is None else f"{fnum((f - 32) / 1.8, 0)}\u202f\u00b0C"


def kmh(mph: float | None) -> str:
    return NA if mph is None else f"{fnum(mph * 1.609, 0)}\u202fkm/h"


def parse_utc(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def stamp(s: str | None) -> str:
    """ISO UTC string -> '17 nov 2026, 21:45 (Madrid)'."""
    if not s:
        return NA
    d = parse_utc(s).astimezone(MADRID)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}, {d:%H:%M} (Madrid)"


def madrid_label(s: str) -> dict[str, str]:
    d = parse_utc(s).astimezone(MADRID)
    e = parse_utc(s).astimezone(EASTERN)
    night = US_NIGHT.get(e.weekday()) if e.hour >= 18 else None
    if e.weekday() == 6 and e.hour >= 19:
        night = "domingo"
    return {
        "day": f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}",
        "day_full": f"{DAYS_FULL[d.weekday()]} {d.day}",
        "short": f"{d.day} {MONTHS[d.month - 1]}",
        "date": d.strftime("%Y-%m-%d"),
        "time": d.strftime("%H:%M"),
        "us_night": night,
    }


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
    }


def _game(
    g: dict,
    odds_game: dict | None,
    odds_meta: dict | None,
    result: dict | None,
    news_items: list[dict] | None = None,
) -> dict:
    home, away = g["home_team"], g["away_team"]
    probs = g["home_win_prob"]
    ph = probs["ensemble"]
    pick_home = ph >= 0.5
    pick = home if pick_home else away
    p_pick = ph if pick_home else 1 - ph
    comps = dict(probs)
    comps["sim"] = g["sim"]["p_home"]
    if odds_game:
        mkt_home = odds_game["consensus_home_prob_shin"]
        mkt_src = f"consenso de {odds_game['n_books']} casas"
    else:
        mkt_home = probs.get("market")
        mkt_src = "línea de cierre"
    mkt_pick = None if mkt_home is None else (mkt_home if pick_home else 1 - mkt_home)
    pure_home = probs.get("ensemble_model_only")
    pure_pick = None if pure_home is None else (pure_home if pick_home else 1 - pure_home)
    # Flag: our models on their own against the market. The published ensemble leans on the
    # market, so its own distance to it says little.
    gap = None if pure_pick is None or mkt_pick is None else pure_pick - mkt_pick
    best = None
    if odds_game:
        side = "best_home_price" if pick_home else "best_away_price"
        best = {**odds_game[side], "name": book_name(odds_game[side]["book"])}
        best["ev"] = p_pick * best["price"] - 1
    margin_pick = g["predicted_margin"] if pick_home else -g["predicted_margin"]
    ml = g["most_likely_score"]
    adj = g.get("news_adjustment") or {"applied": False}
    news = [x for x in (news_items or []) if x["team"] in (home, away)]
    final = None
    if result:
        tot, mar = result["total"], result["result"]
        hs, as_ = int(round((tot + mar) / 2)), int(round((tot - mar) / 2))
        final = {"home": hs, "away": as_, "ok": bool(result.get("ensemble_correct"))}
    flag = gap is not None and abs(gap) >= FLAG_PP
    notes = _notes(g, adj, pick_home)
    return {
        "id": g["game_id"],
        "home": home,
        "away": away,
        "home_name": full(home),
        "away_name": full(away),
        "home_nick": nick(home),
        "away_nick": nick(away),
        "kick": madrid_label(g["kickoff_utc"]),
        "kickoff_utc": g["kickoff_utc"],
        "p_home": ph,
        "pick": pick,
        "pick_home": pick_home,
        "p_pick": p_pick,
        "margin": g["predicted_margin"],
        "margin_pick": margin_pick,
        "margin_txt": fav(home, away, g["predicted_margin"]),
        "total": g["predicted_total"],
        "score_away": ml["away"],
        "score_home": ml["home"],
        "score_prob": ml["prob"],
        "mkt_pick": mkt_pick,
        "mkt_src": mkt_src,
        "pure_pick": pure_pick,
        "gap": gap,
        "edge": None if mkt_pick is None else p_pick - mkt_pick,
        "best": best,
        "comps": comps,
        "market": g["market"],
        "spread_txt": fav(home, away, g["market"]["spread_line"]),
        "sim": g["sim"],
        "model_only_margin": g.get("model_only_margin"),
        "model_only_margin_txt": fav(home, away, g.get("model_only_margin")),
        "factors": _factors(g),
        "reasons": (odds_game or {}).get("likely_reasons", []),
        "flag": flag,
        "flag_text": _flag_text(pick, p_pick, pure_pick, mkt_pick, odds_game),
        "books": _books(odds_game) if odds_game else [],
        "odds_meta": odds_meta,
        "book_spread": (odds_game or {}).get("book_spread_home"),
        "book_total": (odds_game or {}).get("book_total"),
        "generated_at": g["generated_at"],
        "final": final,
        "news": news,
        "adj": adj,
        "adj_text": _adj_text(adj, home, pick_home),
        "note": notes[0] if notes else None,
        "notes": notes,
        "summary": _summary(g, pick, p_pick),
        "score_method": ml.get("method"),
    }


def _adj_text(adj: dict, home: str, pick_home: bool) -> str | None:
    """'Sin X, la probabilidad de HOU baja del 71 % al 66 %.' from the stored audit record."""
    if not adj.get("applied"):
        return None
    a, b = adj["prob_home_before"], adj["prob_home_after"]
    if abs(b - a) < 0.005:
        return None
    names = ", ".join(f"{i['player']} ({STATUS_ES[i['status']].lower()})" for i in adj["items"])
    verb = "baja" if b < a else "sube"
    return f"Con {names}, la probabilidad de {home} {verb} del {fnum(a * 100, 0)}\u202f% al {fnum(b * 100, 0)}\u202f%."


def _flag_text(
    pick: str, p_pick: float, pure: float | None, mkt: float | None, og: dict | None
) -> str | None:
    if pure is None or mkt is None:
        return None
    n = f"las {og['n_books']} casas" if og else "la línea de cierre"
    return (
        f"Sin mirar al mercado, el modelo da a {pick} un {fnum(pure * 100, 0)}\u202f%; {n}, "
        f"un {fnum(mkt * 100, 0)}\u202f%. Nuestro pronóstico final ({fnum(p_pick * 100, 0)}\u202f%) "
        "se apoya sobre todo en el mercado. Cuando ambas lecturas se separan tanto, una de las dos "
        "deja algo fuera."
    )


def _summary(g: dict, pick: str, p_pick: float) -> str:
    """Plain restatement of the numbers; never a claim about how close we are to the market."""
    return (
        f"El ensemble da un {fnum(p_pick * 100, 0)}\u202f% a {nick(pick)}, con un margen previsto "
        f"de {fav(g['home_team'], g['away_team'], g['predicted_margin'])} y {fnum(g['predicted_total'])} "
        "puntos en total."
    )


def _notes(g: dict, adj: dict, pick_home: bool) -> list[dict]:
    """Facts worth a line for this game, most important first. Empty when nothing stands out."""
    c = g["context"]
    home, away = g["home_team"], g["away_team"]
    out: list[dict] = []
    if adj.get("applied") and abs(adj["prob_home_after"] - adj["prob_home_before"]) >= 0.01:
        top = max(adj["items"], key=lambda i: i["points"])
        out.append(
            {
                "icon": "flag",
                "text": f"La ausencia de {top['player']} ({top['team']}) es lo que más mueve el pronóstico.",
            }
        )
    chg = [t for t, k in ((home, "home_qb_change"), (away, "away_qb_change")) if c[k]]
    if chg:
        who = " y ".join(nick(t) for t in chg)
        out.append(
            {
                "icon": "flag",
                "text": f"{who}: cambio de quarterback titular desde su último partido.",
            }
        )
    hr, ar = c["home_rest"], c["away_rest"]
    if hr <= 5 and ar <= 5:
        out.append(
            {"icon": "rest", "text": f"Semana corta para los dos: {hr} y {ar} días de descanso."}
        )
    elif abs(hr - ar) >= 3:
        more, n, m = (home, hr, ar) if hr > ar else (away, ar, hr)
        out.append(
            {"icon": "rest", "text": f"{more} llega con {n} días de descanso y su rival con {m}."}
        )
    km = haversine_km(*HOME_STADIUMS[away], *HOME_STADIUMS[home])
    if km >= 3000:
        out.append({"icon": "trip", "text": f"{away} viaja {fnum(km, 0)} km hasta {home}."})
    if c["dome"]:
        out.append({"icon": "dome", "text": "Se juega a cubierto, sin viento ni lluvia."})
    elif c.get("weather_known"):
        if (c["wind"] or 0) * 1.609 >= 30:
            out.append(
                {
                    "icon": "wind",
                    "text": f"Viento de {kmh(c['wind'])}: se espera menos juego aéreo.",
                }
            )
        if c["temp"] is not None and c["temp"] <= 32:
            out.append({"icon": "cold", "text": f"Hace {c_temp(c['temp'])}: el frío cuenta."})
    if abs(c["home_out_lag"] - c["away_out_lag"]) >= 3:
        more = home if c["home_out_lag"] > c["away_out_lag"] else away
        n, m = max(c["home_out_lag"], c["away_out_lag"]), min(c["home_out_lag"], c["away_out_lag"])
        out.append(
            {
                "icon": "flag",
                "text": f"{more} llega con más bajas en el último parte: {n} frente a {m}.",
            }
        )
    return out


def _books(og: dict) -> list[dict]:
    names = [book_name(k) for k in og["books"]]
    rows = [
        {
            "book": k,
            "name": book_name(k, with_region=names.count(book_name(k)) > 1),
            "p_home": v["p_home_shin"],
            "home_price": v["home_price"],
            "away_price": v["away_price"],
            "edge": v["edge_vs_ours"],
        }
        for k, v in og["books"].items()
    ]
    return sorted(rows, key=lambda r: r["name"].lower())


def _factors(g: dict) -> list[tuple[str, str]]:
    c = g["context"]
    home, away = g["home_team"], g["away_team"]
    km = haversine_km(*HOME_STADIUMS[away], *HOME_STADIUMS[home])
    if c["dome"]:
        venue = "Cubierto o con techo cerrado"
    elif c.get("weather_known"):
        venue = f"Aire libre, {c_temp(c['temp'])}, viento {kmh(c['wind'])}"
    else:
        venue = "Aire libre. El tiempo previsto todavía no entra en el modelo"
    return [
        ("Descanso", f"{home} {c['home_rest']} días, {away} {c['away_rest']} días"),
        ("Viaje del visitante", f"{fnum(km, 0)} km"),
        ("QB titular", _qb(c, home, away)),
        (
            "Bajas en el último parte",
            f"{home} {c['home_out_lag']}, {away} {c['away_out_lag']} "
            "(Out o Doubtful de la semana anterior)",
        ),
        ("Estadio", venue),
    ]


def _qb(c: dict, home: str, away: str) -> str:
    ch = [t for t, k in ((home, "home_qb_change"), (away, "away_qb_change")) if c[k]]
    return (
        "cambio de titular en " + " y ".join(ch) if ch else "sin cambios respecto al último partido"
    )


def game_charts(g: dict) -> dict[str, str]:
    """Margin and total distributions from a fresh deterministic simulation."""
    eh = (g["total"] + g["margin"]) / 2
    ea = (g["total"] - g["margin"]) / 2
    h, a = simulate_games(np.array([eh]), np.array([ea]), n_sims=20000, seed=11, params=SimParams())
    margin = (h - a)[0]
    total = (h + a)[0]
    side = "home" if g["pick_home"] else "away"
    spread = g["market"]["spread_line"]
    tl = g["market"]["total_line"]
    m_chart = charts.histogram(
        margin,
        -35,
        35,
        side,
        spread,
        f"línea {fsigned(spread)}" if spread is not None else "",
        f"{g['away']} gana",
        f"{g['home']} gana",
        "Distribución del margen simulado (local menos visitante)",
    )
    t_chart = charts.histogram(
        total,
        10,
        80,
        None,
        tl,
        f"línea {fnum(tl)}" if tl is not None else "",
        "",
        "puntos totales",
        "Distribución del total de puntos simulado",
        split=None,
    )
    return {
        "margin": m_chart,
        "total": t_chart,
        "p_home_sim": float((h > a).mean() + 0.5 * (h == a).mean()),
    }


# ---------------------------------------------------------------- pages
def _history(inputs: dict) -> dict:
    by_id = {g["game_id"]: g for d in inputs["preds"].values() for g in d["games"]}
    rows = sorted(
        inputs["graded"],
        key=lambda r: by_id[r["game_id"]]["kickoff_utc"] if r["game_id"] in by_id else "",
    )
    out, acc, acc_m, cum, cum_m, brier = [], [], [], 0, 0, 0.0
    for r in rows:
        p = by_id.get(r["game_id"])
        if not p or r["result"] == 0:
            continue
        y = float(r["result"] > 0)
        ph = p["home_win_prob"]["ensemble"]
        pm = p["home_win_prob"].get("market")
        cum += r.get("ensemble_correct", 0)
        brier += (ph - y) ** 2
        n = len(out) + 1
        acc.append(cum / n)
        if pm is not None:
            cum_m += int((pm > 0.5) == (y == 1))
            acc_m.append(cum_m / n)
        out.append(
            {
                **r,
                "pick": r["pick"],
                "p": ph if p["home_win_prob"]["ensemble"] >= 0.5 else 1 - ph,
                "kick": madrid_label(p["kickoff_utc"]),
            }
        )
    n = len(out)
    summ = {
        "n": n,
        "accuracy": cum / n if n else None,
        "brier": brier / n if n else None,
        "market_accuracy": cum_m / n if n and acc_m else None,
    }
    chart = (
        charts.running_lines({"Ensemble": acc, "Mercado": acc_m}, "Acierto acumulado")
        if n >= 2
        else ""
    )
    weeks: dict[tuple, dict] = {}
    for r in out:
        w = weeks.setdefault(
            (r["season"], r["week"]), {"season": r["season"], "week": r["week"], "n": 0, "ok": 0}
        )
        w["n"] += 1
        w["ok"] += r.get("ensemble_correct", 0)
    return {"rows": out, "summary": summ, "chart": chart, "weeks": list(weeks.values())}


def build_site(root: Path | None = None, out: Path | None = None) -> Path:
    root = root or C.ROOT
    out = out or root / "site" / "_build"
    inputs = load_inputs(root)
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    shutil.copytree(HERE / "static", out / "assets", dirs_exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"])
    )
    env.filters.update(num=fnum, signed=fsigned, pct=fpct, pp=fpp, stamp=stamp)
    env.globals["fav"] = fav
    env.globals["status_es"] = STATUS_ES
    now = datetime.now(UTC)
    base_ctx = {
        "generated_at": stamp(now.strftime("%Y-%m-%dT%H:%M:%SZ")),
        "flag_pp": int(FLAG_PP * 100),
        "repo": REPO_URL,
        "full": full,
        "nick": nick,
        "weeks": sorted(inputs["preds"]),
        "comp_labels": COMP_LABELS,
        "has_odds": bool(inputs["odds"]),
    }

    graded_by_id = {r["game_id"]: r for r in inputs["graded"]}
    news_by_week = {k: N.load_news(N.news_path(*k, root=root)) for k in inputs["preds"]}
    week_pages: dict[tuple, list[dict]] = {}
    for key, d in inputs["preds"].items():
        og = {x["game_id"]: x for x in (inputs["odds"].get(key) or {}).get("games", [])}
        meta = inputs["odds"].get(key)
        week_pages[key] = [
            _game(g, og.get(g["game_id"]), meta, graded_by_id.get(g["game_id"]), news_by_week[key])
            for g in d["games"]
        ]
    for games in week_pages.values():
        games.sort(key=lambda x: x["kickoff_utc"])
    current = _current_week(week_pages, now)

    def render(tpl: str, dest: str, rel: str, **ctx: object) -> None:
        path = out / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(env.get_template(tpl).render(rel=rel, **base_ctx, **ctx))

    for key, games in week_pages.items():
        pred = inputs["preds"][key]
        ctx = {
            "season": key[0],
            "week": key[1],
            "games": games,
            "meta": pred,
            "odds_meta": inputs["odds"].get(key),
            "is_current": key == current,
            "flagged": sorted((g for g in games if g["flag"]), key=lambda g: -abs(g["gap"] or 0)),
            "days": _days(games),
            "strip": news_by_week[key],
            "nxt": _next_game(games, now),
            "n_books": max((len(g["books"]) for g in games), default=0),
            "graded": [g for g in games if g["final"]],
        }
        render("week.html", f"jornada/{key[1]}.html", "../", **ctx)
        if key == current:
            render("week.html", "index.html", "", **ctx)
        for g in games:
            ch = game_charts(g)
            render(
                "game.html",
                f"partido/{g['id']}.html",
                "../",
                g=g,
                charts=ch,
                season=key[0],
                week=key[1],
            )
    if current is None:
        render("empty.html", "index.html", "")
    render("history.html", "historial.html", "", hist=_history(inputs))
    bt = inputs["backtest"]
    render(
        "method.html",
        "metodo.html",
        "",
        bt=bt,
        model_labels=MODEL_LABELS,
        calib=charts.calibration(bt["calibration"]["ens"]) if bt else "",
        clv=_clean_clv((bt or {}).get("closing_line_validation")),
    )
    (out / ".nojekyll").write_text("")
    return out


def _days(games: list[dict]) -> list[dict]:
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
        sub = f"{n} partido" + ("s" if n > 1 else "")
        night = d["games"][0]["kick"]["us_night"]
        if n == 1 and night:
            sub += f", {night} noche en EE.\u202fUU."
        d["sub"] = sub
        d["id"] = "d" + d["key"].replace("-", "")
    return list(days.values())


def _next_game(games: list[dict], now: datetime) -> dict | None:
    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    up = [g for g in games if g["kickoff_utc"] > iso]
    return up[0] if up else None


def _clean_clv(clv: dict | None) -> dict | None:
    """The backtest verdict is written in markdown with dot decimals; adapt it for HTML."""
    if not clv:
        return clv
    v = re.sub(r"(\d)\.(\d)", r"\1,\2", clv["verdict"].replace("**", "").replace(" \u2014 ", ", "))
    return {**clv, "verdict": v[:1].upper() + v[1:]}


def _current_week(week_pages: dict[tuple, list[dict]], now: datetime) -> tuple | None:
    if not week_pages:
        return None
    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    upcoming = [
        k for k, gs in sorted(week_pages.items()) if any(g["kickoff_utc"] > iso for g in gs)
    ]
    return upcoming[0] if upcoming else max(week_pages)
