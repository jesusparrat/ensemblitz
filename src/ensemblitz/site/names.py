"""Team and bookmaker display names."""

TEAMS: dict[str, tuple[str, str]] = {
    "ARI": ("Arizona", "Cardinals"),
    "ATL": ("Atlanta", "Falcons"),
    "BAL": ("Baltimore", "Ravens"),
    "BUF": ("Buffalo", "Bills"),
    "CAR": ("Carolina", "Panthers"),
    "CHI": ("Chicago", "Bears"),
    "CIN": ("Cincinnati", "Bengals"),
    "CLE": ("Cleveland", "Browns"),
    "DAL": ("Dallas", "Cowboys"),
    "DEN": ("Denver", "Broncos"),
    "DET": ("Detroit", "Lions"),
    "GB": ("Green Bay", "Packers"),
    "HOU": ("Houston", "Texans"),
    "IND": ("Indianapolis", "Colts"),
    "JAX": ("Jacksonville", "Jaguars"),
    "KC": ("Kansas City", "Chiefs"),
    "LA": ("Los Ángeles", "Rams"),
    "LAC": ("Los Ángeles", "Chargers"),
    "LV": ("Las Vegas", "Raiders"),
    "MIA": ("Miami", "Dolphins"),
    "MIN": ("Minnesota", "Vikings"),
    "NE": ("Nueva Inglaterra", "Patriots"),
    "NO": ("Nueva Orleans", "Saints"),
    "NYG": ("Nueva York", "Giants"),
    "NYJ": ("Nueva York", "Jets"),
    "PHI": ("Filadelfia", "Eagles"),
    "PIT": ("Pittsburgh", "Steelers"),
    "SEA": ("Seattle", "Seahawks"),
    "SF": ("San Francisco", "49ers"),
    "TB": ("Tampa Bay", "Buccaneers"),
    "TEN": ("Tennessee", "Titans"),
    "WAS": ("Washington", "Commanders"),
}


def full(abbr: str) -> str:
    c, n = TEAMS.get(abbr, (abbr, ""))
    return f"{c} {n}".strip()


def nick(abbr: str) -> str:
    return TEAMS.get(abbr, (abbr, abbr))[1]


# The Odds API bookmaker keys -> (display name, region suffix used only to tell duplicates apart)
BOOKS: dict[str, tuple[str, str]] = {
    "betano_uk": ("Betano", "UK"),
    "betanysports": ("BetAnySports", ""),
    "betclic_fr": ("Betclic", "FR"),
    "betfair_ex_eu": ("Betfair Exchange", "UE"),
    "betfair_ex_uk": ("Betfair Exchange", "UK"),
    "betfair_sb_uk": ("Betfair Sportsbook", "UK"),
    "betfred_uk": ("Betfred", "UK"),
    "betmgm": ("BetMGM", ""),
    "betonlineag": ("BetOnline.ag", ""),
    "betrivers": ("BetRivers", ""),
    "betsson": ("Betsson", ""),
    "betus": ("BetUS", ""),
    "betvictor": ("BetVictor", ""),
    "betway": ("Betway", ""),
    "bovada": ("Bovada", ""),
    "boylesports": ("BoyleSports", ""),
    "casumo": ("Casumo", ""),
    "codere_it": ("Codere", "IT"),
    "coolbet": ("Coolbet", ""),
    "coral": ("Coral", ""),
    "draftkings": ("DraftKings", ""),
    "everygame": ("Everygame", ""),
    "fanduel": ("FanDuel", ""),
    "gtbets": ("GTbets", ""),
    "ladbrokes_uk": ("Ladbrokes", "UK"),
    "leovegas": ("LeoVegas", ""),
    "leovegas_se": ("LeoVegas", "SE"),
    "lowvig": ("LowVig.ag", ""),
    "marathonbet": ("Marathonbet", ""),
    "matchbook": ("Matchbook", ""),
    "mybookieag": ("MyBookie.ag", ""),
    "nordicbet": ("NordicBet", ""),
    "paddypower": ("Paddy Power", ""),
    "pinnacle": ("Pinnacle", ""),
    "pmu_fr": ("PMU", "FR"),
    "smarkets": ("Smarkets", ""),
    "sport888": ("888sport", ""),
    "tipico_de": ("Tipico", "DE"),
    "unibet_nl": ("Unibet", "NL"),
    "unibet_se": ("Unibet", "SE"),
    "unibet_uk": ("Unibet", "UK"),
    "williamhill": ("William Hill", ""),
}


def book_name(key: str, with_region: bool = False) -> str:
    """Human name for a bookmaker key; unknown keys are title-cased instead of shown raw."""
    name, region = BOOKS.get(key, (key.replace("_", " ").title(), ""))
    return f"{name} ({region})" if with_region and region else name
