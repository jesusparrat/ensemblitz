"""Canonical prediction contract v1: schema, conventions, provenance and validation.

The single source of truth for the shape of ``predictions/`` is
``schemas/predictions.v1.schema.json``; this module reads it, validates documents against it
(a small JSON Schema subset, so no new dependency) and adds the checks a schema cannot express.
Conventions are explained in ``docs/CONTRACT.md``.

The reader, the ledger and the writer live in ``contract_io.py`` and ``ledger.py``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ensemblitz import config as C

SCHEMA_VERSION = "1"
# Next to the code, not under ENSEMBLITZ_ROOT: the schema is part of the source tree.
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "predictions.v1.schema.json"

# Conventions (see docs/CONTRACT.md). Data is always UTC; only the site converts.
MARGIN_CONVENTION = "home_minus_away"
DISPLAY_TZ = {"es": "Europe/Madrid", "en": "America/New_York"}
MARKET_SOURCES = ("nflverse_line", "odds_api_consensus")
# Inputs hashed into ``data_snapshot``: every parquet file `ensemblitz update` writes to data/raw.
DEFAULT_SNAPSHOT_GLOB = "data/raw/*.parquet"


class ContractError(ValueError):
    """A document does not follow the contract."""


class DirtyTreeError(RuntimeError):
    """Production provenance was requested from a working tree with uncommitted changes."""


# ---------------------------------------------------------------- schema
def load_schema(path: Path | None = None) -> dict:
    return json.loads((path or SCHEMA_PATH).read_text())


def _resolve(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise ContractError(f"unsupported $ref {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _type_ok(value: object, kind: str) -> bool:
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if kind == "null":
        return value is None
    raise ContractError(f"unsupported type {kind!r}")


def _check(value: object, node: dict, root: dict, path: str, errors: list[str]) -> None:
    """Validate ``value`` against the JSON Schema subset used by the contract."""
    if "$ref" in node:
        _check(value, _resolve(node["$ref"], root), root, path, errors)
        return
    if "anyOf" in node:
        for option in node["anyOf"]:
            sub: list[str] = []
            _check(value, option, root, path, sub)
            if not sub:
                return
        errors.append(f"{path}: matches no allowed form")
        return
    if "const" in node and value != node["const"]:
        errors.append(f"{path}: must be {node['const']!r}, got {value!r}")
        return
    if "enum" in node and value not in node["enum"]:
        errors.append(f"{path}: {value!r} is not one of {node['enum']}")
        return
    if "type" in node and not _type_ok(value, node["type"]):
        errors.append(f"{path}: expected {node['type']}, got {type(value).__name__}")
        return
    if isinstance(value, float) and not math.isfinite(value):
        errors.append(f"{path}: NaN or infinity is not allowed (use null)")
        return
    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in node and value < node["minimum"]:
            errors.append(f"{path}: {value} is below {node['minimum']}")
        if "maximum" in node and value > node["maximum"]:
            errors.append(f"{path}: {value} is above {node['maximum']}")
    if isinstance(value, str):
        if "pattern" in node and not re.search(node["pattern"], value):
            errors.append(f"{path}: {value!r} does not match {node['pattern']}")
        if "minLength" in node and len(value) < node["minLength"]:
            errors.append(f"{path}: shorter than {node['minLength']}")
    if isinstance(value, list):
        if "minItems" in node and len(value) < node["minItems"]:
            errors.append(f"{path}: fewer than {node['minItems']} items")
        if "maxItems" in node and len(value) > node["maxItems"]:
            errors.append(f"{path}: more than {node['maxItems']} items")
        if "items" in node:
            for i, item in enumerate(value):
                _check(item, node["items"], root, f"{path}[{i}]", errors)
    if isinstance(value, dict):
        if "minProperties" in node and len(value) < node["minProperties"]:
            errors.append(f"{path}: fewer than {node['minProperties']} entries")
        for key in node.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required field {key!r}")
        props = node.get("properties", {})
        patterns = node.get("patternProperties", {})
        for key, item in value.items():
            sub_path = f"{path}.{key}"
            if key in props:
                _check(item, props[key], root, sub_path, errors)
                continue
            matched = [p for p in patterns if re.search(p, key)]
            for p in matched:
                _check(item, patterns[p], root, sub_path, errors)
            if not matched and node.get("additionalProperties", True) is False:
                errors.append(f"{path}: unexpected field {key!r}")


def schema_errors(doc: object, schema: dict | None = None) -> list[str]:
    """Structural errors of ``doc`` against the v1 schema (empty list = valid)."""
    schema = schema or load_schema()
    errors: list[str] = []
    _check(doc, schema, schema, "$", errors)
    return errors


def semantic_errors(doc: dict) -> list[str]:
    """Rules the schema cannot express. Assumes the document is structurally valid."""
    errors: list[str] = []
    season, week = doc["season"], doc["week"]
    seen: set[str] = set()
    for i, g in enumerate(doc["games"]):
        p = f"$.games[{i}]"
        gid = g["game_id"]
        if gid in seen:
            errors.append(f"{p}: duplicated game_id {gid}")
        seen.add(gid)
        expected = f"{season}_{week:02d}_{g['away_team']}_{g['home_team']}"
        if gid != expected:
            errors.append(f"{p}: game_id {gid} does not match season/week/away/home ({expected})")
        if g["generated_at_utc"] > doc["generated_at_utc"]:
            errors.append(f"{p}: generated after the snapshot itself")
        dist = g["headline"]["distribution"]
        for key in ("home_points", "away_points", "margin_home", "total"):
            lo, hi = dist[key]
            if lo > hi:
                errors.append(f"{p}.headline.distribution.{key}: q10 above q90")
        sources = [q["source"] for q in g["market"]]
        if len(sources) != len(set(sources)):
            errors.append(f"{p}.market: one quote per source")
    if doc["data_cutoff_utc"] > doc["generated_at_utc"]:
        errors.append("$: data_cutoff_utc is later than generated_at_utc")
    return errors


def validate_week(doc: object, schema: dict | None = None) -> list[str]:
    """All contract errors of a v1 week document (empty list = valid)."""
    errors = schema_errors(doc, schema)
    if errors:
        return errors
    assert isinstance(doc, dict)
    return semantic_errors(doc)


# ---------------------------------------------------------------- versions
def detect_version(doc: object) -> str:
    """``"1"`` for a contract v1 document, ``"0"`` for the files written before it.

    v0 (2026 weeks 11 and 12) has no ``schema_version``; it is recognised by its own shape:
    a ``generated_at`` header and games with a ``home_win_prob`` dict. Reading v0 into the v1
    model is PR 1b; here it is only detected so nothing mistakes one for the other.
    """
    if not isinstance(doc, dict):
        raise ContractError("a predictions file is a JSON object")
    if "schema_version" in doc:
        if doc["schema_version"] == SCHEMA_VERSION:
            return SCHEMA_VERSION
        raise ContractError(f"unknown schema_version {doc['schema_version']!r}")
    games = doc.get("games")
    if (
        isinstance(games, list)
        and "generated_at" in doc
        and all(isinstance(g, dict) and isinstance(g.get("home_win_prob"), dict) for g in games)
    ):
        return "0"
    raise ContractError("not a predictions file: neither contract v1 nor the legacy v0 shape")


# ---------------------------------------------------------------- derived values
def margin_home(headline: dict) -> float:
    """Headline margin, home minus away, from the two expected points (never stored twice)."""
    return headline["home_points"] - headline["away_points"]


def total(headline: dict) -> float:
    return headline["home_points"] + headline["away_points"]


def pick(game: dict) -> str:
    """The headline pick: the home team at 50% or more, as the pipeline has always done."""
    return game["home_team"] if game["headline"]["home_win_prob"] >= 0.5 else game["away_team"]


def odds_api_margin_home(point: float | None) -> float | None:
    """The Odds API spread ``point`` (negative = home favoured) as a home margin."""
    return None if point is None else -float(point)


# ---------------------------------------------------------------- provenance
def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True, timeout=30
    )
    return out.stdout.strip()


def git_state(root: Path | None = None) -> tuple[str, bool]:
    """(HEAD commit SHA, whether the working tree is clean). Untracked files count as dirty;
    ignored files (``data/``, ``.venv``) do not."""
    root = root or C.ROOT
    sha = _git(root, "rev-parse", "HEAD")
    dirty = _git(root, "status", "--porcelain")
    return sha, dirty == ""


def provenance(root: Path | None = None, production: bool = False) -> dict[str, object]:
    """``git_sha`` and ``reproducible`` for a new artifact.

    In production the tree must be clean, otherwise the SHA would not describe the code that
    ran: :class:`DirtyTreeError` is raised. Outside production the artifact is always flagged
    ``reproducible: false``, clean tree or not, so a local run can never pass for a published one.
    """
    sha, clean = git_state(root)
    if production and not clean:
        raise DirtyTreeError(
            "uncommitted changes: commit or stash them before producing a published artifact"
        )
    return {"git_sha": sha, "reproducible": bool(production and clean)}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def data_snapshot(paths: Iterable[Path] | None = None, root: Path | None = None) -> dict[str, str]:
    """SHA-256 of each input parquet, keyed by its POSIX path relative to ``root``, sorted."""
    root = (root or C.ROOT).resolve()
    files = sorted(root.glob(DEFAULT_SNAPSHOT_GLOB)) if paths is None else list(paths)
    if not files:
        raise ContractError(f"no input files to hash under {root / DEFAULT_SNAPSHOT_GLOB}")
    out = {}
    for f in files:
        f = Path(f).resolve()
        if f.suffix != ".parquet":
            raise ContractError(f"{f.name}: only parquet inputs are part of the snapshot")
        out[f.relative_to(root).as_posix()] = sha256_file(f)
    return dict(sorted(out.items()))


def _as_utc_timestamp(value: object):
    """Parse a parquet cell into an aware UTC datetime, or None."""
    from datetime import UTC, date, datetime

    if value is None:
        return None
    try:
        import pandas as pd
    except ImportError:
        pd = None
    if pd is not None and pd.isna(value):
        return None
    if isinstance(value, datetime):
        dt = value
        return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if pd is not None:
        ts = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    return None


def data_cutoff_utc(
    paths: Iterable[Path] | None = None, root: Path | None = None, now: object | None = None
) -> str:
    """Latest timestamp *inside* the input parquets, never the run clock.

    Used as ``data_cutoff_utc`` on a v1 snapshot. Future scheduled kickoffs are
    ignored: only already-observed times count (datetime columns such as
    ``date_modified``, and the kickoff of games that already have a result).
    ``generated_at_utc`` still records when the run happened.
    """
    from datetime import UTC, datetime

    import pandas as pd

    from ensemblitz.data.load import kickoff_utc as _kickoff_utc

    root = (root or C.ROOT).resolve()
    files = sorted(root.glob(DEFAULT_SNAPSHOT_GLOB)) if paths is None else list(paths)
    if not files:
        raise ContractError(f"no input files to hash under {root / DEFAULT_SNAPSHOT_GLOB}")
    clock = now or datetime.now(UTC)
    if not isinstance(clock, datetime):
        raise ContractError("now must be a datetime")
    clock = clock.replace(tzinfo=UTC) if clock.tzinfo is None else clock.astimezone(UTC)
    latest = None
    for f in files:
        f = Path(f).resolve()
        if f.suffix != ".parquet":
            continue
        df = pd.read_parquet(f)
        for col in df.columns:
            series = df[col]
            if not (
                pd.api.types.is_datetime64_any_dtype(series)
                or pd.api.types.is_datetime64tz_dtype(series)
            ):
                continue
            converted = pd.to_datetime(series, utc=True, errors="coerce")
            value = converted.max()
            if pd.isna(value):
                continue
            dt = value.to_pydatetime()
            if dt <= clock:
                latest = dt if latest is None else max(latest, dt)
        # Played games: their kickoff is an observed time, unlike future gamedays.
        if "result" in df.columns and "gameday" in df.columns:
            played = df[df["result"].notna()].copy()
            if not played.empty:
                kicks = pd.to_datetime(_kickoff_utc(played), utc=True, errors="coerce")
                value = kicks.max()
                if not pd.isna(value):
                    dt = value.to_pydatetime()
                    if dt <= clock:
                        latest = dt if latest is None else max(latest, dt)
    if latest is None:
        raise ContractError("no observed timestamps found in the input parquets")
    return latest.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [
    "DISPLAY_TZ",
    "MARGIN_CONVENTION",
    "MARKET_SOURCES",
    "SCHEMA_VERSION",
    "ContractError",
    "DirtyTreeError",
    "data_cutoff_utc",
    "data_snapshot",
    "detect_version",
    "git_state",
    "load_schema",
    "margin_home",
    "odds_api_margin_home",
    "pick",
    "provenance",
    "schema_errors",
    "semantic_errors",
    "sha256_file",
    "total",
    "validate_week",
]
