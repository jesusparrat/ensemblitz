"""Gate before commit/deploy: refuse to publish garbage or secrets. Exit 1 on any problem.

Usage: python scripts/validate_outputs.py [--site site/_build]
Checks predictions/, reports/, results/, models/ JSON (finite numbers, sane probabilities,
non-empty weeks, required odds-report schema and governance) and scans outputs (and the built
site, if given) for credential patterns.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(
    r"(apikey=|api_key=|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gh[ousr]_[A-Za-z0-9]{20,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16})",
    re.I,
)
ODDS_REQUIRED_TOP = (
    "season",
    "week",
    "market_source",
    "market_type",
    "consensus_method",
    "odds_fetched_at",
    "predictions_generated_at",
    "games",
)
ODDS_REQUIRED_GAME = (
    "game_id",
    "home",
    "away",
    "model_only_home_prob",
    "consensus_home_prob_shin",
    "gap_model_only",
    "n_books",
)
ODDS_FORBIDDEN_GAME = frozenset(
    {
        "our_home_prob",
        "edge",
        "books",
        "best_home_price",
        "best_away_price",
        "ev_per_unit_best",
        "best_side",
        "book_spread_home",
        "book_total",
        "consensus_home_prob_mult",
        "our_margin_minus_book",
        "our_cover_prob_home",
    }
)
errors: list[str] = []


def _bad_const(name: str) -> None:
    raise ValueError(f"non-finite value {name}")


def load(path: Path):
    try:
        return json.loads(path.read_text(), parse_constant=_bad_const)
    except Exception as exc:
        errors.append(f"{path.relative_to(ROOT)}: {exc}")


def prob_ok(x) -> bool:
    return x is None or (
        isinstance(x, (int, float))
        and not isinstance(x, bool)
        and math.isfinite(x)
        and 0.0 <= x <= 1.0
    )


def required_prob_ok(x) -> bool:
    return (
        isinstance(x, (int, float))
        and not isinstance(x, bool)
        and math.isfinite(x)
        and 0.0 <= x <= 1.0
    )


def validate_odds_report(d: object, label: str) -> list[str]:
    """Validate an aggregate odds report against required fields and governance constraints."""
    errs: list[str] = []
    if not isinstance(d, dict):
        return [f"{label}: expected JSON object"]
    for key in ODDS_REQUIRED_TOP:
        if key not in d or d[key] is None:
            errs.append(f"{label}: missing required field {key}")
    games = d.get("games")
    if not isinstance(games, list):
        return errs + [f"{label}: games must be a list"]
    for idx, g in enumerate(games):
        if not isinstance(g, dict):
            errs.append(f"{label}: games[{idx}] must be an object")
            continue
        gid = g.get("game_id") or f"games[{idx}]"
        for key in ODDS_REQUIRED_GAME:
            if key not in g or g[key] is None:
                errs.append(f"{label}: {gid} missing required field {key}")
        for key in ("model_only_home_prob", "consensus_home_prob_shin"):
            if key in g and g[key] is not None and not required_prob_ok(g[key]):
                errs.append(f"{label}: {gid} invalid {key}={g[key]}")
        gap = g.get("gap_model_only")
        if gap is not None and (
            isinstance(gap, bool)
            or not isinstance(gap, (int, float))
            or not math.isfinite(gap)
            or not -1.0 <= gap <= 1.0
        ):
            errs.append(f"{label}: {gid} invalid gap_model_only={gap}")
        n_books = g.get("n_books")
        if n_books is not None and (
            isinstance(n_books, bool) or not isinstance(n_books, int) or n_books < 1
        ):
            errs.append(f"{label}: {gid} invalid n_books={n_books}")
        bad = sorted(ODDS_FORBIDDEN_GAME.intersection(g))
        if bad:
            errs.append(f"{label}: {gid} contains forbidden odds fields {bad}")
    return errs


def check_predictions() -> None:
    from ensemblitz import contract as K
    from ensemblitz import ledger as L

    files = L.iter_snapshot_paths(ROOT)
    if not files:
        errors.append("predictions/: no files")
    for p in files:
        d = load(p)
        if not d:
            continue
        rel = p.relative_to(ROOT)
        if not d.get("games"):
            errors.append(f"{rel}: empty week")
            continue
        try:
            version = K.detect_version(d)
        except K.ContractError as exc:
            errors.append(f"{rel}: {exc}")
            continue
        if version == K.SCHEMA_VERSION:
            for e in K.validate_week(d):
                errors.append(f"{rel}: {e}")
            continue
        for g in d.get("games", []):
            for k, val in g.get("home_win_prob", {}).items():
                if not prob_ok(val):
                    errors.append(f"{rel}: {g.get('game_id')} home_win_prob.{k}={val}")
            m = g.get("predicted_margin")
            if m is not None and abs(m) > 60:
                errors.append(f"{rel}: {g.get('game_id')} absurd margin {m}")
            tot = g.get("predicted_total")
            if tot is not None and not 10 <= tot <= 100:
                errors.append(f"{rel}: {g.get('game_id')} absurd total {tot}")


def check_json_tree() -> None:
    for sub in ("reports", "results", "models"):
        for p in sorted((ROOT / sub).rglob("*.json")):
            load(p)
    for p in sorted((ROOT / "reports" / "odds").glob("*_week*.json")):
        d = load(p)
        if d is not None:
            errors.extend(validate_odds_report(d, p.name))


def scan_secrets(folders: list[Path]) -> None:
    for folder in folders:
        for p in folder.rglob("*"):
            if p.is_file() and p.suffix in {".json", ".md", ".html", ".js", ".css", ".txt"}:
                m = SECRET.search(p.read_text(errors="ignore"))
                if m:
                    errors.append(
                        f"{p.relative_to(ROOT)}: secret-like pattern '{m.group(0)[:8]}...'"
                    )


def check_integrity() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verify_integrity", ROOT / "scripts" / "verify_integrity.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    errors.extend(mod.verify(ROOT))


def main() -> int:
    check_predictions()
    check_json_tree()
    check_integrity()
    folders = [ROOT / f for f in ("predictions", "reports", "results", "models")]
    if "--site" in sys.argv:
        folders.append(Path(sys.argv[sys.argv.index("--site") + 1]))
    scan_secrets([f for f in folders if f.exists()])
    for e in errors:
        print("FAIL", e)
    print("validate_outputs:", "FAILED" if errors else "ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
