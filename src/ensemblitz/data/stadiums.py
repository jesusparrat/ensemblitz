"""Stadium coordinates (for travel distance now, hourly weather later via Open-Meteo)."""

from __future__ import annotations

import math

import pandas as pd

# team -> (latitude, longitude, is_dome_or_closed_roof_by_default)
HOME_STADIUMS: dict[str, tuple[float, float]] = {
    "ARI": (33.5276, -112.2626),
    "ATL": (33.7554, -84.4008),
    "BAL": (39.2780, -76.6227),
    "BUF": (42.7738, -78.7870),
    "CAR": (35.2258, -80.8528),
    "CHI": (41.8623, -87.6167),
    "CIN": (39.0954, -84.5160),
    "CLE": (41.5061, -81.6995),
    "DAL": (32.7473, -97.0945),
    "DEN": (39.7439, -105.0201),
    "DET": (42.3400, -83.0456),
    "GB": (44.5013, -88.0622),
    "HOU": (29.6847, -95.4107),
    "IND": (39.7601, -86.1639),
    "JAX": (30.3239, -81.6373),
    "KC": (39.0489, -94.4839),
    "LA": (33.9535, -118.3392),
    "LAC": (33.9535, -118.3392),
    "LV": (36.0909, -115.1833),
    "MIA": (25.9580, -80.2389),
    "MIN": (44.9737, -93.2577),
    "NE": (42.0909, -71.2643),
    "NO": (29.9511, -90.0812),
    "NYG": (40.8135, -74.0745),
    "NYJ": (40.8135, -74.0745),
    "PHI": (39.9008, -75.1675),
    "PIT": (40.4468, -80.0158),
    "SEA": (47.5952, -122.3316),
    "SF": (37.4030, -121.9700),
    "TB": (27.9759, -82.5033),
    "TEN": (36.1665, -86.7713),
    "WAS": (38.9076, -76.8645),
}

# Neutral / international venues keyed by nflverse stadium_id.
NEUTRAL_VENUES: dict[str, tuple[float, float]] = {
    "LON00": (51.5560, -0.2796),
    "LON01": (51.4560, -0.3415),
    "LON02": (51.6043, -0.0664),
    "MEX00": (19.3029, -99.1505),
    "GER00": (48.2188, 11.6247),
    "FRA00": (50.0686, 8.6455),
    "SAO00": (-23.5453, -46.4742),
    "MEL00": (-37.8200, 144.9834),
    "RIO00": (-22.9121, -43.2302),
    "PAR00": (48.9245, 2.3601),
    "MAD01": (40.4531, -3.6883),
    "MUN01": (48.2188, 11.6247),
    "DUB00": (53.3351, -6.2287),
}


def venue_coords(stadium_id: str | None, home_team: str, neutral: bool) -> tuple[float, float]:
    """Coordinates of the venue of a game."""
    if neutral and stadium_id in NEUTRAL_VENUES:
        return NEUTRAL_VENUES[stadium_id]
    if neutral and isinstance(stadium_id, str):
        # Domestic neutral sites (e.g. a Super Bowl host): fall back to the home base listed.
        return HOME_STADIUMS[home_team]
    return HOME_STADIUMS[home_team]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def stadium_table() -> pd.DataFrame:
    """Flat table with every known venue; handy for the future weather module."""
    rows = [(k, "home", v[0], v[1]) for k, v in HOME_STADIUMS.items()]
    rows += [(k, "neutral", v[0], v[1]) for k, v in NEUTRAL_VENUES.items()]
    return pd.DataFrame(rows, columns=["key", "kind", "lat", "lon"])
