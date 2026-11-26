"""Language support for the static site: number/date formats and the string tables.

Spanish is the default language (served at the site root); English lives under ``en/``.
Every UI string sits in ``strings.py``; nothing user-facing is hard-coded in templates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from markupsafe import Markup

from ensemblitz.site.strings import STRINGS

LANGS = ("es", "en")
DEFAULT = "es"
MADRID = ZoneInfo("Europe/Madrid")
EASTERN = ZoneInfo("America/New_York")
MINUS = "−"
NNBSP = " "

DAYS = {
    "es": ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}
DAYS_FULL = {
    "es": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
MONTHS = {
    "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}
US_NIGHT = {3: "thu", 0: "mon"}  # NFL standalone prime-time nights, US Eastern


def parse_utc(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


class Lang:
    """Formatting and string lookup for one language."""

    def __init__(self, code: str) -> None:
        if code not in STRINGS:
            raise ValueError(f"unknown language {code!r}")
        self.code = code
        self.table = STRINGS[code]
        self.na = self.table["na"]
        self.tz = MADRID if code == "es" else EASTERN

    # ------------------------------------------------------------ strings
    def t(self, key: str, **kw: object) -> Markup:
        """String by key. Placeholders are HTML-escaped unless they are already Markup."""
        return Markup(self.table[key]).format(**kw) if kw else Markup(self.table[key])

    def text(self, key: str, **kw: object) -> str:
        """Plain (unescaped) text, for attributes and non-HTML use."""
        s = self.table[key]
        return s.format(**kw) if kw else s

    # ------------------------------------------------------------ numbers
    def n(self, x: float | None, nd: int = 1) -> str:
        if x is None:
            return self.na
        s = f"{x:.{nd}f}".replace("-", MINUS)
        return s.replace(".", ",") if self.code == "es" else s

    def signed(self, x: float | None, nd: int = 1) -> str:
        if x is None:
            return self.na
        s = self.n(x, nd)
        return ("+" if round(x, nd) > 0 else "") + s

    def pct(self, x: float | None, nd: int = 0) -> str:
        """A probability (0..1) as a percentage."""
        if x is None:
            return self.na
        return self.pct_int(x * 100, nd)

    def pct_int(self, v: float, nd: int = 0) -> str:
        return f"{self.n(v, nd)}{NNBSP + '%' if self.code == 'es' else '%'}"

    def rng(self, lo: float, hi: float) -> str:
        return f"{int(round(lo))}–{int(round(hi))}"

    def fav(self, home: str, away: str, margin_home: float | None, nd: int = 1) -> str:
        """Predicted winning margin: favourite with positive margin ('HOU +8,7' / 'HOU +8.7')."""
        if margin_home is None:
            return self.na
        if abs(margin_home) < 0.05:
            return self.table["even"]
        return f"{home if margin_home > 0 else away} +{self.n(abs(margin_home), nd)}"

    def spread_line(self, home: str, away: str, margin_home: float | None, nd: int = 1) -> str:
        """Literal betting-line quote: favourite with negative spread ('HOU −12,5')."""
        if margin_home is None:
            return self.na
        if abs(margin_home) < 0.05:
            return self.table["even"]
        return f"{home if margin_home > 0 else away} {MINUS}{self.n(abs(margin_home), nd)}"

    def margin_point(self, home: str, away: str, margin_home: float) -> str:
        """Single integer margin endpoint in positive winning-margin convention ('IND +10')."""
        v = int(round(margin_home))
        if v == 0:
            return self.table["tie"]
        return f"{home} +{v}" if v > 0 else f"{away} +{abs(v)}"

    def margin_range(self, home: str, away: str, lo_home: float, hi_home: float) -> str:
        """80% margin range ordered strictly away -> home (matching the histogram X-axis)."""
        lo_val, hi_val = (lo_home, hi_home) if lo_home <= hi_home else (hi_home, lo_home)
        return self.text(
            "game.margin_range",
            lo=self.margin_point(home, away, lo_val),
            hi=self.margin_point(home, away, hi_val),
        )

    # ------------------------------------------------------------ dates
    def clock(self, d: datetime) -> str:
        """24-hour clock in Spanish, 12-hour AM/PM clock in English."""
        if self.code == "es":
            return f"{d:%H:%M}"
        hour = (d.hour % 12) or 12
        suffix = "AM" if d.hour < 12 else "PM"
        return f"{hour}:{d.minute:02d} {suffix}"

    def stamp(self, s: str | None) -> str:
        """ISO UTC string to Madrid (es) or Eastern (en) date and time."""
        if not s:
            return self.na
        d = parse_utc(s).astimezone(self.tz)
        mon = MONTHS[self.code][d.month - 1]
        if self.code == "es":
            return f"{d.day} {mon} {d.year}, {self.clock(d)} (Madrid)"
        return f"{mon} {d.day}, {d.year}, {self.clock(d)} ET"

    def kick(self, s: str) -> dict[str, str | None]:
        d = parse_utc(s).astimezone(self.tz)
        e = parse_utc(s).astimezone(EASTERN)
        night = US_NIGHT.get(e.weekday()) if e.hour >= 18 else None
        if e.weekday() == 6 and e.hour >= 19:
            night = "sun"
        mon = MONTHS[self.code][d.month - 1]
        dm = f"{d.day} {mon}" if self.code == "es" else f"{mon} {d.day}"
        return {
            "day": f"{DAYS[self.code][d.weekday()]} {dm}",
            "day_full": f"{DAYS_FULL[self.code][d.weekday()]} {dm}"
            if self.code == "en"
            else f"{DAYS_FULL['es'][d.weekday()]} {d.day}",
            "short": dm,
            "wd": DAYS[self.code][d.weekday()],
            "date": d.strftime("%Y-%m-%d"),
            "time": self.clock(d),
            "us_night": self.table.get(f"night_{night}") if night else None,
        }

    def temp_c(self, f: float | None) -> str:
        return self.na if f is None else f"{self.n((f - 32) / 1.8, 0)}{NNBSP}°C"

    def kmh(self, mph: float | None) -> str:
        return self.na if mph is None else f"{self.n(mph * 1.609, 0)}{NNBSP}km/h"
