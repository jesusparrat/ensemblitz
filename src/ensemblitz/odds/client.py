"""The Odds API v4 client with a Parquet cache and quota awareness.

Free tier: 500 requests/month. We make one request per run and refuse to call again if the last
cached response is recent or the quota headers say we are nearly out. The key is read from the
``ODDS_API_KEY`` environment variable and is never logged or written to disk.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

import pandas as pd

from ensemblitz import config as C

log = logging.getLogger(__name__)

BASE = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
REGIONS = "eu,uk,us"
MARKETS = "h2h,spreads,totals"
MIN_REMAINING = 20  # keep a reserve of requests
MIN_HOURS_BETWEEN_CALLS = 6  # one call per run, and runs are weekly or manual

ODDS_DIR = C.DATA_DIR / "odds"
QUOTA_FILE = ODDS_DIR / "quota.json"


def flatten(events: list[dict], fetched_at: str) -> pd.DataFrame:
    """API JSON -> one row per bookmaker/market/outcome."""
    rows = []
    for ev in events:
        for bk in ev.get("bookmakers", []):
            for mk in bk.get("markets", []):
                for oc in mk.get("outcomes", []):
                    rows.append(
                        {
                            "event_id": ev["id"],
                            "commence_time": ev["commence_time"],
                            "home_name": ev["home_team"],
                            "away_name": ev["away_team"],
                            "bookmaker": bk["key"],
                            "market": mk["key"],
                            "outcome": oc["name"],
                            "price": oc["price"],
                            "point": oc.get("point"),
                            "last_update": mk.get("last_update"),
                            "fetched_at": fetched_at,
                        }
                    )
    return pd.DataFrame(rows)


def latest_cache() -> pd.DataFrame | None:
    files = sorted(ODDS_DIR.glob("odds_*.parquet")) if ODDS_DIR.exists() else []
    return pd.read_parquet(files[-1]) if files else None


def _recent_call(now: datetime) -> bool:
    files = sorted(ODDS_DIR.glob("odds_*.parquet")) if ODDS_DIR.exists() else []
    if not files:
        return False
    stamp = datetime.strptime(files[-1].stem.removeprefix("odds_"), "%Y%m%dT%H%M%SZ").replace(
        tzinfo=UTC
    )
    return now - stamp < timedelta(hours=MIN_HOURS_BETWEEN_CALLS)


def fetch_odds(force: bool = False) -> tuple[pd.DataFrame | None, str]:
    """Return (odds frame, status message). Never raises on a missing key or quota problem."""
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        return latest_cache(), "ODDS_API_KEY not set: live fetch skipped"
    now = datetime.now(UTC)
    if not force and _recent_call(now):
        return latest_cache(), "recent cached response reused (quota protection)"
    if QUOTA_FILE.exists():
        q = json.loads(QUOTA_FILE.read_text())
        if q.get("remaining") is not None and q["remaining"] < MIN_REMAINING:
            return latest_cache(), f"quota low ({q['remaining']} requests left): not calling"
    url = (
        BASE
        + "?"
        + urllib.parse.urlencode(
            {
                "apiKey": key,
                "regions": REGIONS,
                "markets": MARKETS,
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            }
        )
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 (fixed https URL)
            events = json.loads(resp.read())
            remaining = resp.headers.get("x-requests-remaining")
            used = resp.headers.get("x-requests-used")
    except urllib.error.HTTPError as exc:
        return latest_cache(), f"The Odds API returned HTTP {exc.code}: using cache if any"
    except (urllib.error.URLError, TimeoutError) as exc:
        return (
            latest_cache(),
            f"The Odds API unreachable ({type(exc).__name__}): using cache if any",
        )
    ODDS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    df = flatten(events, now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    df.to_parquet(ODDS_DIR / f"odds_{stamp}.parquet", index=False)
    QUOTA_FILE.write_text(
        json.dumps(
            {
                "remaining": int(remaining) if remaining else None,
                "used": int(used) if used else None,
                "checked_at": stamp,
            }
        )
    )
    return df, f"fetched {len(events)} events; requests remaining: {remaining}"
