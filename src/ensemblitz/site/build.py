"""Render predictions/, results/ and reports/ into a static, bilingual site.

Spanish pages live at the site root, English pages under ``en/``. The data layer
(``_game``, ``_history``) is language independent; text is produced per language through
``i18n.Lang`` and the string tables in ``strings.py``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from ensemblitz import config as C
from ensemblitz import contract_io
from ensemblitz import ledger as L
from ensemblitz import news as N
from ensemblitz.data.stadiums import HOME_STADIUMS, haversine_km
from ensemblitz.site import charts, og
from ensemblitz.site.i18n import LANGS, Lang
from ensemblitz.site.names import full

HERE = Path(__file__).parent
REPO_URL = "https://github.com/jesusparrat/ensemblitz"
DEFAULT_BASE_URL = "https://jesusparrat.github.io/ensemblitz"
GOATCOUNTER_CODE_RE = re.compile(r"^[a-z0-9-]+$")
FLAG_PP = 10  # fixed >= 10 printed percentage points gap that marks a reading disagreement
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
    pred_meta = {}
    for art in L.iter_latest(root):
        loaded = contract_io.load_week(art.path)
        key = (loaded.doc["season"], loaded.doc["week"])
        doc = dict(loaded.doc)
        doc["generated_at"] = doc["generated_at_utc"]  # alias for existing templates
        preds[key] = doc
        pred_meta[key] = {
            "headline_kind": loaded.headline_kind,
            "headline_kinds": loaded.headline_kinds,
            "version": loaded.version,
            "path": art.rel,
            "sha256": loaded.sha256,
        }
    odds = {}
    for p in sorted((root / "reports" / "odds").glob("*_week*.json")):
        d = json.loads(p.read_text())
        odds[(d["season"], d["week"])] = d
    graded = []
    for p in sorted((root / "results").glob("*/week*.json")):
        graded += json.loads(p.read_text())
    return {
        "preds": preds,
        "pred_meta": pred_meta,
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
    fr, dr = (
        (c["home_rest_days"], c["away_rest_days"])
        if pick_home
        else (c["away_rest_days"], c["home_rest_days"])
    )
    if fr - dr >= 3:
        return {"key": "why_rest", "team": fav, "n": fr, "m": dr}
    km = haversine_km(*HOME_STADIUMS[away], *HOME_STADIUMS[home])
    if pick_home and km >= 3000:
        return {"key": "why_trip", "team": dog, "km": km, "home": home}
    wind = c.get("wind_mph", c.get("wind"))
    if not c["dome"] and c.get("weather_known") and (wind or 0) * 1.609 >= 30:
        return {"key": "why_wind", "wind": wind}
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
        venue = {
            "v": "open",
            "temp": c.get("temp_f", c.get("temp")),
            "wind": c.get("wind_mph", c.get("wind")),
        }
    else:
        venue = {"v": "open_nowx"}
    return [
        {
            "k": "rest",
            "home": home,
            "away": away,
            "h": c.get("home_rest_days", c.get("home_rest")),
            "a": c.get("away_rest_days", c.get("away_rest")),
        },
        {"k": "trip", "away": away, "km": km},
        {"k": "qb", "teams": chg},
        {"k": "venue", **venue},
    ]


def _game(
    g: dict,
    odds_game: dict | None,
    result: dict | None,
    news_items: list[dict] | None = None,
    headline_kind: str = "model_only",
    odds_fetched_at: str | None = None,
) -> dict:
    """Language independent view of one game; the headline is the published number."""
    home, away = g["home_team"], g["away_team"]
    h = g["headline"]
    legacy = headline_kind == "ensemble"
    ph, hp, ap = h["home_win_prob"], h["home_points"], h["away_points"]
    hp, ap = round(hp, 1), round(ap, 1)
    margin_d, total_d = round(hp - ap, 1), round(hp + ap, 1)
    pick_home = ph >= 0.5
    fav = home if pick_home else away
    p_win = ph if pick_home else 1 - ph
    agree = (margin_d > 0) == pick_home and abs(margin_d) >= 0.05
    nfl = contract_io.market_quote(g, "nflverse_line") or {}
    cons = contract_io.market_quote(g, "odds_api_consensus")
    if odds_game:
        mkt_home = odds_game["consensus_home_prob_shin"]
        mkt_n = odds_game["n_books"]
        mkt_source = "odds_api_consensus"
        mkt_is_closing = False
        mkt_time = odds_fetched_at
        mkt_time_kind = "fetched" if odds_fetched_at else None
    elif cons and cons.get("home_win_prob") is not None:
        mkt_home = cons["home_win_prob"]
        mkt_n = cons.get("n_books") or 0
        mkt_source = "odds_api_consensus"
        mkt_is_closing = bool(cons.get("is_closing", False))
        mkt_time = cons.get("captured_at_utc")
        mkt_time_kind = "captured" if mkt_time else None
    elif nfl.get("home_win_prob") is not None:
        mkt_home = nfl.get("home_win_prob")
        mkt_n = 0
        mkt_source = "nflverse_line"
        mkt_is_closing = bool(nfl.get("is_closing", False))
        mkt_time = nfl.get("captured_at_utc")
        mkt_time_kind = "read" if mkt_time else None
    else:
        mkt_home, mkt_n = None, 0
        mkt_source, mkt_is_closing, mkt_time, mkt_time_kind = None, False, None, None
    mkt_win = None if mkt_home is None else (mkt_home if pick_home else 1 - mkt_home)
    diff = gap_pts(p_win, mkt_win)
    ens_p = g["ensemble"]["home_win_prob"]
    ens = ens_p if pick_home else 1 - ens_p
    dist = h.get("distribution") or {}
    rng = None
    # Legacy (pre-web-v2) picks never showed a range: they had no model_only.sim.
    if (not legacy) and dist.get("margin_home") and dist["margin_home"][0] is not None:
        rng = {
            "home": (dist["home_points"][0], dist["home_points"][1]),
            "away": (dist["away_points"][0], dist["away_points"][1]),
            "margin": (dist["margin_home"][0], dist["margin_home"][1]),
            "total": (dist["total"][0], dist["total"][1]),
        }
    final = None
    if result:
        tot, mar = result["total"], result["result"]
        final = {
            "home": int(round((tot + mar) / 2)),
            "away": int(round((tot - mar) / 2)),
            "ok": bool(result.get("headline_correct", result.get("ensemble_correct"))),
        }
    # Per docs/CONTRACT.md §3, market is not a model component and is shown once in its own block.
    comps = {k: g["components"].get(k) for k in ("elo", "kf", "lgbm", "lgbm_mkt")}
    comps["ensemble_model_only"] = h["home_win_prob"]
    comps["ensemble"] = ens_p

    def side(p: float | None) -> float | None:
        return None if p is None else (p if pick_home else 1 - p)

    expl = g.get("explanation")
    inj_ctx = (
        expl["injury_context"] if isinstance(expl, dict) and expl.get("injury_context") else None
    )
    ab = inj_ctx if inj_ctx is not None else (g.get("absences") or {"home": [], "away": []})
    market_view = {
        "spread_line": nfl.get("margin_home"),
        "total_line": nfl.get("total_line"),
        "home_moneyline": nfl.get("home_moneyline"),
        "away_moneyline": nfl.get("away_moneyline"),
        "captured_at_utc": nfl.get("captured_at_utc"),
        "is_closing": bool(nfl.get("is_closing", False)),
    }
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
        "mkt_source": mkt_source,
        "mkt_is_closing": mkt_is_closing,
        "mkt_time": mkt_time,
        "mkt_time_kind": mkt_time_kind,
        "diff": diff,
        "flag": diff is not None and abs(diff) >= FLAG_PP,
        "ens_win": ens,
        "comps": {k: side(v) for k, v in comps.items()},
        "market": market_view,
        "why": _why(g, home, away, pick_home, abs(margin_d)),
        "explanation": expl,
        "injury_cutoff_utc": inj_ctx["cutoff_utc"] if inj_ctx is not None else None,
        "facts": _facts(g),
        "absences": [
            {**a, "team": team}
            for team, key in ((home, "home"), (away, "away"))
            for a in ab.get(key, [])
        ],
        "example": h["example_score"],
        "saved_at": g["generated_at_utc"],
        "final": final,
        "news": [x for x in (news_items or []) if x["team"] in (home, away)],
        "histogram": (dist.get("histogram") if dist else None),
    }


def game_charts(g: dict, L: Lang) -> dict[str, str]:
    """Margin and total distributions from the stored histogram. Never re-simulates."""
    hist = g.get("histogram")
    if not hist:
        return {"margin": "", "total": ""}
    side = "home" if g["pick_home"] else "away"
    spread, tl = g["market"]["spread_line"], g["market"]["total_line"]
    m_chart = charts.histogram_from_counts(
        hist["margin_home"],
        side,
        spread,
        L.text("chart.line", v=L.spread_line(g["home"], g["away"], spread))
        if spread is not None
        else "",
        L.text("chart.wins", team=g["away"]),
        L.text("chart.wins", team=g["home"]),
        L.text("chart.margin_aria"),
    )
    t_chart = charts.histogram_from_counts(
        hist["total"],
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
    kinds = {}
    for meta in inputs.get("pred_meta", {}).values():
        kinds.update(meta.get("headline_kinds") or {})
    for r in rows:
        p = by_id[r["game_id"]]
        headline = r.get("headline")
        if not headline or isinstance(headline, dict):
            headline = kinds.get(p["game_id"]) or "ensemble"
        ok = r.get("headline_correct", r.get("ensemble_correct"))
        if ok is None:
            continue
        if isinstance(p.get("headline"), dict):
            ph = (
                p["headline"]["home_win_prob"]
                if headline == "model_only"
                else p["ensemble"]["home_win_prob"]
            )
        else:
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
                "saved_at": p.get("generated_at_utc") or p.get("generated_at"),
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
            "saved_at": d.get("generated_at_utc") or d.get("generated_at"),
            "n": len(d["games"]),
            "first_kick": min(g["kickoff_utc"] for g in d["games"]),
            "headline": inputs["pred_meta"].get(k, {}).get("headline_kind")
            or (
                "model_only"
                if isinstance((d["games"] or [{}])[0].get("headline"), dict)
                else (d["games"] or [{}])[0].get("headline") or "ensemble"
            ),
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


# ---------------------------------------------------------------- SEO & analytics helpers
def resolve_base_url(base_url: str | None = None) -> str:
    """Resolve and validate the public site base URL (no trailing slash)."""
    raw = os.environ.get("SITE_BASE_URL", "") if base_url is None else base_url
    cleaned = raw.strip().rstrip("/") or DEFAULT_BASE_URL
    parsed = urlsplit(cleaned)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"invalid SITE_BASE_URL: {raw!r} (expected http:// or https:// URL)")
    return cleaned


def resolve_goatcounter_code(code: str | None = None) -> str | None:
    """Resolve optional GoatCounter site code; returns None when disabled, raises if invalid."""
    raw = os.environ.get("ENSEMBLITZ_GOATCOUNTER_CODE", "") if code is None else code
    cleaned = raw.strip()
    if not cleaned:
        return None
    if not GOATCOUNTER_CODE_RE.fullmatch(cleaned):
        raise ValueError(f"invalid ENSEMBLITZ_GOATCOUNTER_CODE: {raw!r} (must match ^[a-z0-9-]+$)")
    return cleaned


def build_csp(goatcounter_code: str | None) -> Markup:
    """Build the Content-Security-Policy header; zero external domains unless analytics is set."""
    script_src = "'self'"
    connect_src = "'none'"
    if goatcounter_code:
        if not GOATCOUNTER_CODE_RE.fullmatch(goatcounter_code):
            raise ValueError(
                f"invalid ENSEMBLITZ_GOATCOUNTER_CODE: {goatcounter_code!r} "
                "(must match ^[a-z0-9-]+$)"
            )
        script_src = "'self' https://gc.zgo.at"
        connect_src = f"https://{goatcounter_code}.goatcounter.com"
    return Markup(
        f"default-src 'none'; script-src {script_src}; style-src 'self' 'unsafe-inline'; "
        f"font-src 'self'; img-src 'self' data:; connect-src {connect_src}; "
        "object-src 'none'; base-uri 'none'; form-action 'none'"
    )


def abs_url(base_url: str, dest: str) -> str:
    """Convert a built relative path to its canonical absolute URL."""
    clean = dest.lstrip("/")
    if clean == "index.html":
        return f"{base_url}/"
    if clean.endswith("/index.html"):
        return f"{base_url}/{clean[: -len('index.html')]}"
    return f"{base_url}/{clean}"


def _domain_label(base_url: str) -> str:
    """Short human-readable host/path label for OG card footers."""
    parsed = urlsplit(base_url)
    return (parsed.netloc + parsed.path).rstrip("/")


# ---------------------------------------------------------------- build
class Site:
    """One build: renders every page in every language."""

    def __init__(
        self,
        root: Path,
        out: Path,
        *,
        base_url: str | None = None,
        goatcounter_code: str | None = None,
    ) -> None:
        self.root, self.out = root, out
        self.base_url = resolve_base_url(base_url)
        self.goatcounter_code = resolve_goatcounter_code(goatcounter_code)
        self.csp = build_csp(self.goatcounter_code)
        self.rendered_pages: list[dict[str, object]] = []
        self.inputs = load_inputs(root)
        self.env = Environment(
            loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"])
        )
        self.now = datetime.now(UTC)
        saved_stamps = [
            d.get("generated_at_utc") or d.get("generated_at")
            for d in self.inputs["preds"].values()
            if d.get("generated_at_utc") or d.get("generated_at")
        ]
        cutoff_stamps = [
            d["data_cutoff_utc"] for d in self.inputs["preds"].values() if d.get("data_cutoff_utc")
        ]
        self.saved_stamp = max(saved_stamps) if saved_stamps else "1970-01-01T00:00:00Z"
        # v1 snapshots carry data_cutoff_utc; legacy v0 snapshots fall back to generated_at_utc.
        self.data_stamp = max(cutoff_stamps) if cutoff_stamps else self.saved_stamp

    def render(
        self,
        L: Lang,
        tpl: str,
        kind: str,
        key: object = None,
        *,
        og_title: str | None = None,
        og_description: str | None = None,
        og_image_rel: str | None = None,
        og_image_alt: str | None = None,
        **ctx: object,
    ) -> None:
        dest = ROUTES[L.code][kind].format(key)
        rel = "../" * dest.count("/")

        def u(k: str, kk: object = None) -> str:
            return rel + ROUTES[L.code][k].format(kk)

        alt = {
            c: rel + ROUTES[c][kind].format(key)
            for c in LANGS  # relative twin path for the interactive language switch
        }
        alt_abs = {
            c: abs_url(self.base_url, ROUTES[c][kind].format(key))
            for c in LANGS  # absolute twin URLs for canonical/hreflang/sitemap
        }
        canonical_url = abs_url(self.base_url, dest)
        image_rel = og_image_rel or og.home_card_rel(L.code)
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
            spread_txt=L.spread_line,
            margin_rng=L.margin_range,
            stamp=L.stamp,
            full=full,
            shown=shown_pct,
            why_text=lambda g: why_text(L, g),
            absence_list=lambda g: absence_list(L, g),
            news_status=lambda s: L.text(f"status_{s}"),
            u=u,
            rel=rel,
            alt=alt,
            alt_abs=alt_abs,
            canonical_url=canonical_url,
            og_title=og_title or f"{L.text('site.title')} | ensemblitz",
            og_description=og_description or L.text("site.description"),
            og_image_url=abs_url(self.base_url, image_rel),
            og_image_alt=og_image_alt or L.text("og.alt_home"),
            csp=self.csp,
            goatcounter_code=self.goatcounter_code,
            other=next(c for c in LANGS if c != L.code),
            page_kind=kind,
            data_at=L.stamp(self.data_stamp),
            generated_at=L.stamp(self.saved_stamp),
            repo=REPO_URL,
            flag_pts=FLAG_PP,
            weeks=sorted(self.inputs["preds"]),
            **ctx,
        )
        path = self.out / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.rendered_pages.append({"dest": dest, "url": canonical_url, "alt_abs": alt_abs})

    def build(self) -> Path:
        out, inputs = self.out, self.inputs
        self.rendered_pages = []
        if out.exists():
            shutil.rmtree(out)
        (out / "assets").mkdir(parents=True)
        shutil.copytree(HERE / "static", out / "assets", dirs_exist_ok=True)
        news_by_week = {k: N.load_news(N.news_path(*k, root=self.root)) for k in inputs["preds"]}
        week_pages: dict[tuple, list[dict]] = {}
        for key, d in inputs["preds"].items():
            odds_doc = inputs["odds"].get(key) or {}
            odds_games = {x["game_id"]: x for x in odds_doc.get("games", [])}
            odds_fetched_at = odds_doc.get("odds_fetched_at")
            graded = {r["game_id"]: r for r in inputs["graded"]}
            kinds = inputs["pred_meta"].get(key, {}).get("headline_kinds") or {}
            default_kind = inputs["pred_meta"].get(key, {}).get("headline_kind", "model_only")
            week_pages[key] = sorted(
                (
                    _game(
                        g,
                        odds_games.get(g["game_id"]),
                        graded.get(g["game_id"]),
                        news_by_week[key],
                        kinds.get(g["game_id"], default_kind),
                        odds_fetched_at=odds_fetched_at,
                    )
                    for g in d["games"]
                ),
                key=lambda x: x["kick_utc"],
            )
        current = _current_week(week_pages, self.now)
        hist = _history(inputs)
        domain_label = _domain_label(self.base_url)
        for code in LANGS:
            L = Lang(code)
            og.generate_og_cards(
                out,
                L,
                week_pages,
                current,
                flag_pp=FLAG_PP,
                domain_label=domain_label,
            )
            self._pages(L, week_pages, news_by_week, current, hist)
        self._write_sitemap()
        self._write_robots()
        (out / ".nojekyll").write_text("", encoding="utf-8")
        return out

    def _write_sitemap(self) -> None:
        """Write deterministic XML sitemap covering all ES and EN rendered HTML pages."""
        lastmod = self.saved_stamp[:10] if self.saved_stamp[:4] != "1970" else None
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">',
        ]
        for entry in sorted(self.rendered_pages, key=lambda item: str(item["url"])):
            url = xml_escape(str(entry["url"]))
            alt_abs = entry["alt_abs"]
            assert isinstance(alt_abs, dict)
            lines.append("  <url>")
            lines.append(f"    <loc>{url}</loc>")
            if lastmod:
                lines.append(f"    <lastmod>{xml_escape(lastmod)}</lastmod>")
            lines.append(
                f'    <xhtml:link rel="alternate" hreflang="es" href="{xml_escape(alt_abs["es"])}"/>'
            )
            lines.append(
                f'    <xhtml:link rel="alternate" hreflang="en" href="{xml_escape(alt_abs["en"])}"/>'
            )
            lines.append(
                f'    <xhtml:link rel="alternate" hreflang="x-default" '
                f'href="{xml_escape(alt_abs["es"])}"/>'
            )
            lines.append("  </url>")
        lines.append("</urlset>\n")
        (self.out / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")

    def _write_robots(self) -> None:
        """Write robots.txt pointing crawlers to the absolute sitemap.xml URL."""
        body = f"User-agent: *\nAllow: /\n\nSitemap: {self.base_url}/sitemap.xml\n"
        (self.out / "robots.txt").write_text(body, encoding="utf-8")

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
            week_img = og.week_card_rel(key[0], key[1], L.code)
            self.render(
                L,
                "week.html",
                "week",
                key[1],
                og_title=f"{L.text('week.title', week=key[1])} | ensemblitz",
                og_description=L.text("og.desc_week", week=key[1], season=key[0]),
                og_image_rel=week_img,
                og_image_alt=L.text("og.alt_week", week=key[1], season=key[0]),
                **ctx,
            )
            if key == current:
                self.render(
                    L,
                    "week.html",
                    "home",
                    None,
                    og_title=f"{L.text('week.title', week=key[1])} | ensemblitz",
                    og_description=L.text("site.description"),
                    og_image_rel=og.home_card_rel(L.code),
                    og_image_alt=L.text("og.alt_home"),
                    **ctx,
                )
            for g in games:
                self.render(
                    L,
                    "game.html",
                    "game",
                    g["id"],
                    og_title=f"{g['away']} {L.text('card.at')} {g['home']} | ensemblitz",
                    og_description=L.text(
                        "game.description",
                        away=g["away_name"],
                        home=g["home_name"],
                        fav=g["fav"],
                        p=L.pct(g["p_win"]),
                    ),
                    og_image_rel=week_img,
                    og_image_alt=L.text(
                        "og.alt_game",
                        away=g["away"],
                        home=g["home"],
                        week=key[1],
                        season=key[0],
                    ),
                    g=g,
                    charts=game_charts(g, L),
                    season=key[0],
                    week=key[1],
                    facts=[fact_text(L, f) for f in g["facts"]],
                )
        if current is None:
            self.render(
                L,
                "empty.html",
                "home",
                og_title=f"{L.text('empty.title')} | ensemblitz",
                og_description=L.text("site.description"),
                og_image_rel=og.home_card_rel(L.code),
                og_image_alt=L.text("og.alt_home"),
            )
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
        self.render(
            L,
            "history.html",
            "history",
            og_title=f"{L.text('hist.title')} | ensemblitz",
            og_description=L.text("og.desc_history"),
            og_image_rel=og.home_card_rel(L.code),
            og_image_alt=L.text("og.alt_history"),
            **hist_ctx,
        )
        bt, bl = inputs["backtest"], inputs["baseline"]
        calib_pts = None
        if bl and (bl.get("deciles") or {}).get("model_only"):
            calib_pts = bl["deciles"]["model_only"]
        elif bt and (bt.get("calibration") or {}).get("ens"):
            calib_pts = bt["calibration"]["ens"]
        pop = (bl or {}).get("population") or {}
        scored_n = pop.get("n_scored") or (bl or {}).get("n_games")
        if scored_n is None and bt:
            scored_n = bt["overall"]["market"]["n"]
        played_n = pop.get("n_played") or (bt or {}).get("n_games") or scored_n
        ties_n = pop.get("n_ties")
        if ties_n is None and played_n is not None and scored_n is not None:
            ties_n = played_n - scored_n
        self.render(
            L,
            "method.html",
            "method",
            og_title=f"{L.text('method.title')} | ensemblitz",
            og_description=L.text("og.desc_method"),
            og_image_rel=og.home_card_rel(L.code),
            og_image_alt=L.text("og.alt_method"),
            bt=bt,
            bl=bl,
            pop_scored=scored_n,
            pop_played=played_n,
            pop_ties=ties_n,
            model_labels={k: L.text(f"model_{k}") for k in MODEL_KEYS},
            calib=charts.calibration(
                calib_pts,
                L.text("calib.x"),
                L.text("calib.y"),
                L.text("calib.aria"),
            )
            if calib_pts
            else "",
        )


def build_site(
    root: Path | None = None,
    out: Path | None = None,
    *,
    base_url: str | None = None,
    goatcounter_code: str | None = None,
) -> Path:
    root = root or C.ROOT
    return Site(
        root,
        out or root / "site" / "_build",
        base_url=base_url,
        goatcounter_code=goatcounter_code,
    ).build()


def why_text(L: Lang, g: dict) -> Markup:
    """One plain sentence for the game summary, in the reader's language.

    For v1 snapshots with a pre-computed ``explanation`` block, formats the largest
    descriptive pre-game unit mismatch and the leading stack component (plus any QB
    change) without recomputing attributions in the site layer. Legacy v0 snapshots
    without ``explanation`` fall back to the earlier input rule.
    """
    expl = g.get("explanation")
    if isinstance(expl, dict) and expl.get("matchups") and expl.get("summary"):
        top = expl["matchups"][0]
        summ = expl["summary"]
        unit_label = L.text(f"unit_{top['unit']}")
        comp_label = L.text(f"comp_short_{summ['lead_component']}")
        qb_teams = summ.get("qb_change_teams") or []
        if qb_teams:
            return L.t(
                "why_v1_qb",
                qb_teams=" / ".join(qb_teams),
                unit=unit_label,
                off=top["off_team"],
                off_rank=top["off_rank"],
                dfn=top["def_team"],
                def_rank=top["def_rank"],
                comp=comp_label,
            )
        return L.t(
            "why_v1",
            unit=unit_label,
            off=top["off_team"],
            off_rank=top["off_rank"],
            dfn=top["def_team"],
            def_rank=top["def_rank"],
            comp=comp_label,
        )
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
    """Group games by local calendar day (Madrid on /es/, US Eastern on /en/)."""
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
