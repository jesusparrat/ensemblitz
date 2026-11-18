"""Drive-level game, with play-by-play only in the clutch window.

Most of the game is one draw per possession: touchdown, field goal, punt,
turnover or end of half, plus a drive length. The last four minutes of the
fourth quarter, and the last two minutes of the first half, switch to plays
when the margin is within 8. That window is where a field goal makes a final
margin of 3 and a touchdown makes a 7.

Neutral site turns off the home touchdown shift. There is no travel, altitude
or weather term. Stars are a fixed log-odds nudge used only to check that
removing a starter lowers that team's win probability.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from ensemblitz.sim.drive_fit import PRIOR, DriveBook

# Last 4:00 of the fourth quarter, and last 2:00 of the second, within 8 points.
CLUTCH_Q4 = 240
CLUTCH_Q2 = 120
CLUTCH_MARGIN = 8
# Share of would-be touchdowns kicked as field goals on the last drive of a half
# when the offence is tied or down by at most 3. Chosen on 2017 only.
LATE_FG_INSTEAD = 0.50
# 2015-2017, scrimmage plays with at most four minutes left in the fourth.
PASS_RATE = {"trail": 0.86, "tie": 0.66, "lead": 0.21}
COMP, SACK, INT = 0.55, 0.061, 0.034
RUN_MEAN, RUN_SD = 3.92, 4.4
COMP_MEAN, COMP_SD = 11.2, 8.5
# Fourth down, 2015-2017. Rows: yardline red / field-goal range / long.
# Columns: distance short (<=3) / long. Values are P(go), P(FG); the rest punt.
FOURTH = np.array(
    [
        [[0.369, 0.631], [0.098, 0.902]],
        [[0.450, 0.509], [0.132, 0.746]],
        [[0.170, 0.001], [0.053, 0.001]],
    ]
)
# One game-day shock on the TD log-odds, independent per team. Set so the 2017
# pooled margin SD lands near the real season; not refit on 2018-2025.
GAME_SHOCK = 0.22

# Synthetic starters. A negative TD log-odds hurts the offence. "opp" raises the
# opponent's TD log-odds (the defender is missing).
STARS = {
    "QB1": ("td", -0.70),
    "WR1": ("td", -0.40),
    "LT1": ("td", -0.35),
    "EDGE1": ("opp", 0.40),
    "CB1": ("opp", 0.35),
}


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _softmax(logp: np.ndarray) -> np.ndarray:
    z = logp - logp.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


@dataclass(frozen=True)
class Matchup:
    """Per-game possession distributions. Axis 1 is the offence (0 home, 1 away)."""

    p: np.ndarray  # (G, 2, script, outcome)
    sec: np.ndarray  # (G, 2, script) mean drive seconds
    is_neutral: np.ndarray  # (G,)
    ot_both: np.ndarray  # (G,) 2025 regular-season overtime
    td_logit: np.ndarray  # (G, 2) clutch talent, home-field already applied


def _mix(off: np.ndarray, de: np.ndarray, league: np.ndarray) -> np.ndarray:
    """Log-additive opponent adjustment. Equal to the league when both sides are average."""
    logp = (
        np.log(np.clip(off, 1e-4, None))
        + np.log(np.clip(de, 1e-4, None))
        - np.log(np.clip(league, 1e-4, None))
    )
    return _softmax(logp)


def from_book(
    book: DriveBook,
    home: np.ndarray,
    away: np.ndarray,
    season: np.ndarray,
    is_neutral: np.ndarray | bool = False,
) -> Matchup:
    from ensemblitz.sim.drive_fit import TEAM_INDEX

    h = np.array([TEAM_INDEX[t] for t in home])
    a = np.array([TEAM_INDEX[t] for t in away])
    off_h, off_a = book.mix(h, "off"), book.mix(a, "off")
    def_h, def_a = book.mix(h, "de"), book.mix(a, "de")
    league = book.mix(np.arange(len(book.acc.off)), "off").mean(axis=0)
    # Home offence meets the away defence. League is the same shape as one side.
    p = np.stack([_mix(off_h, def_a, league), _mix(off_a, def_h, league)], axis=1)
    sec_h, _ = book.seconds(h)
    sec_a, _ = book.seconds(a)
    sec = np.stack([sec_h, sec_a], axis=1)
    neutral = np.broadcast_to(np.asarray(is_neutral, bool), len(home)).copy()
    hfa = 0.0 if False else book.hfa_logit()
    td = np.stack(
        [
            _logit(p[:, 0, 1, 0]) - _logit(PRIOR[0]),
            _logit(p[:, 1, 1, 0]) - _logit(PRIOR[0]),
        ],
        axis=1,
    )
    if hfa:
        td = td + np.where(neutral[:, None], 0.0, np.array([hfa, -hfa]))
        hfa_side = np.where(neutral[:, None], 0.0, np.array([hfa, -hfa]))
        shift = np.zeros_like(p)
        shift[:, :, :, 0] = hfa_side[:, :, None]
        p = _softmax(np.log(np.clip(p, 1e-4, None)) + shift)
    ot = np.asarray(season) >= 2025
    return Matchup(p=p, sec=np.clip(sec, 40, 220), is_neutral=neutral, ot_both=ot, td_logit=td)


def with_star_out(match: Matchup, side: int, role: str) -> Matchup:
    """Copy with one synthetic starter missing for ``side`` (0 home, 1 away)."""
    kind, amount = STARS[role]
    logp = np.log(np.clip(match.p, 1e-4, None))
    if kind == "td":
        logp[:, side, :, 0] += amount
    else:
        logp[:, 1 - side, :, 0] += amount
    p = _softmax(logp)
    td = match.td_logit.copy()
    if kind == "td":
        td[:, side] += amount
    else:
        td[:, 1 - side] += amount
    return replace(match, p=p, td_logit=td)


def _fg_make(dist: np.ndarray) -> np.ndarray:
    return np.clip(1.0 / (1.0 + np.exp((dist - 52.0) / 7.0)), 0.12, 0.97)


def _sample_disc(cdf_last_axis: np.ndarray, u: np.ndarray) -> np.ndarray:
    return (u[..., None] < cdf_last_axis).argmax(axis=-1)


class _State:
    def __init__(self, match: Matchup, n: int, rng: np.random.Generator):
        g = match.p.shape[0]
        self.m = match
        self.rng = rng
        self.G, self.S = g, n
        shp = (g, n)
        self.home = np.zeros(shp, np.int16)
        self.away = np.zeros(shp, np.int16)
        self.qtr = np.ones(shp, np.int8)
        self.clock = np.full(shp, 900.0)
        self.poss = np.zeros(shp, np.int8)
        self.alive = np.ones(shp, bool)
        self.clutch = np.zeros(shp, bool)
        self.down = np.ones(shp, np.int8)
        self.dist = np.full(shp, 10.0)
        self.yl = np.full(shp, 75.0)
        self.running = np.zeros(shp, bool)
        self.to_h = np.full(shp, 3, np.int8)
        self.to_a = np.full(shp, 3, np.int8)
        self.ot_h = np.zeros(shp, bool)
        self.ot_a = np.zeros(shp, bool)
        self.shock = rng.normal(0.0, GAME_SHOCK, size=(g, n, 2))
        receive = rng.random(shp) < 0.5
        self.poss = receive.astype(np.int8)
        self.recv0 = self.poss.copy()

    def _diff(self) -> np.ndarray:
        return np.where(self.poss == 0, self.home - self.away, self.away - self.home).astype(float)

    def _script(self, diff: np.ndarray) -> np.ndarray:
        return np.where(diff <= -7, 0, np.where(diff >= 7, 2, 1)).astype(np.int8)

    def _probs(self, script: np.ndarray) -> np.ndarray:
        # (G, S, 5)
        base = self.m.p[np.arange(self.G)[:, None], self.poss, script]
        logp = np.log(np.clip(base, 1e-4, None))
        logp[..., 0] += self.shock[
            np.arange(self.G)[:, None], np.arange(self.S)[None, :], self.poss
        ]
        z = logp - logp.max(axis=-1, keepdims=True)
        e = np.exp(z)
        return e / e.sum(axis=-1, keepdims=True)

    def _add(self, pts: np.ndarray, mask: np.ndarray, offence_home: np.ndarray) -> None:
        self.home += np.where(mask & offence_home, pts, 0).astype(np.int16)
        self.away += np.where(mask & ~offence_home, pts, 0).astype(np.int16)

    def _td_points(self, mask: np.ndarray) -> np.ndarray:
        # A touchdown is 7. Sampling the extra point smears the 3 and the 7.
        return np.where(mask, 7, 0).astype(np.int16)

    def _start_ot(self, mask: np.ndarray) -> None:
        self.qtr = np.where(mask, 5, self.qtr)
        self.clock = np.where(mask, 600.0, self.clock)
        self.clutch = np.where(mask, False, self.clutch)
        self.to_h = np.where(mask, 2, self.to_h)
        self.to_a = np.where(mask, 2, self.to_a)
        self.ot_h = np.where(mask, False, self.ot_h)
        self.ot_a = np.where(mask, False, self.ot_a)
        self.poss = np.where(
            mask, (self.rng.random((self.G, self.S)) < 0.5).astype(np.int8), self.poss
        )
        self.running = np.where(mask, False, self.running)

    def _score_drive(self, mask: np.ndarray, kind: np.ndarray) -> None:
        """kind: 0 TD, 1 FG, 2 punt, 3 turnover, 4 end of half."""
        off_home = self.poss == 0
        td = mask & (kind == 0)
        fg = mask & (kind == 1)
        # End-of-half in the counts is a no-score drive (kneel or the clock died).
        # The clock was already reduced by the drive length; it is not zeroed here.
        change = mask & (kind >= 2)
        self._add(self._td_points(td), td, off_home)
        self._add(np.where(fg, 3, 0).astype(np.int16), fg, off_home)
        self.poss = np.where(td | fg | change, 1 - self.poss, self.poss)
        self._maybe_ot_end(td, is_td=True)
        self._maybe_ot_end(fg, is_td=False)

    def _maybe_ot_end(self, scored: np.ndarray, is_td: bool) -> None:
        ot = scored & self.alive & (self.qtr == 5)
        if not np.any(ot):
            return
        # Possession already flipped, so the scorer is the other side.
        scorer_home = self.poss == 1
        self.ot_h |= ot & scorer_home
        self.ot_a |= ot & ~scorer_home
        both = self.ot_h & self.ot_a
        other = np.where(scorer_home, self.ot_a, self.ot_h)
        ahead = self.home != self.away
        # Through 2024 an opening touchdown ends it. A field goal does not.
        first_td = ot & is_td & ~other & ~self.m.ot_both[:, None]
        sudden = ot & both & ahead
        self.alive &= ~first_td & ~sudden

    def drive(self, mask: np.ndarray) -> None:
        if not np.any(mask):
            return
        diff = self._diff()
        script = self._script(diff)
        probs = self._probs(script)
        # Tied game: more field goals, fewer touchdowns. Moves final margins from 7 toward 3.
        tied = diff == 0
        probs = probs.copy()
        probs[..., 0] = np.where(tied, probs[..., 0] * 0.55, probs[..., 0])
        probs[..., 1] = np.where(tied, probs[..., 1] * 1.70, probs[..., 1])
        probs = probs / probs.sum(axis=-1, keepdims=True)
        cdf = np.cumsum(probs, axis=-1)
        cdf[..., -1] = 1.0
        kind = _sample_disc(cdf, self.rng.random((self.G, self.S))).astype(np.int8)
        sec = self.m.sec[np.arange(self.G)[:, None], self.poss, script]
        # Leading drives burn a bit more clock: the 2015-16 mix, not a new rule.
        sec = np.where(script == 2, sec * 1.08, sec)
        sec = np.where(script == 0, sec * 0.94, sec)
        dur = np.clip(self.rng.normal(sec, 48.0), 20.0, 280.0)
        end_half = ((self.qtr == 2) | (self.qtr == 4) | (self.qtr == 5)) & (dur >= self.clock)
        # A score counts only when it lands before the clock dies.
        lands = self.rng.random((self.G, self.S)) * dur < self.clock
        kind = np.where(end_half & ~lands, 4, kind)
        late_points = (
            mask
            & ((self.qtr == 2) | (self.qtr == 4))
            & (self.clock <= 180)
            & (diff == 0)
            & (kind == 0)
        )
        take = late_points & (self.rng.random((self.G, self.S)) < LATE_FG_INSTEAD)
        kind = np.where(take, 1, kind)
        dur = np.where(end_half, self.clock, dur)
        spill = ((self.qtr == 1) | (self.qtr == 3)) & (dur >= self.clock) & mask
        self.clock = np.where(mask, self.clock - dur, self.clock)
        self.qtr = np.where(spill, self.qtr + 1, self.qtr)
        self.clock = np.where(spill, self.clock + 900.0, self.clock)
        self._score_drive(mask, kind)
        died = mask & (self.clock <= 0) & ~spill
        self._end_quarter(died)

    def _end_quarter(self, mask: np.ndarray) -> None:
        mask = mask & self.alive
        if not np.any(mask):
            return
        q1 = mask & (self.qtr == 1)
        q3 = mask & (self.qtr == 3)
        half = mask & (self.qtr == 2)
        reg = mask & (self.qtr == 4)
        ot = mask & (self.qtr == 5)
        self.qtr = np.where(q1, 2, self.qtr)
        self.qtr = np.where(q3, 4, self.qtr)
        cont = q1 | q3
        self.clock = np.where(cont, 900.0, self.clock)
        self.clutch = np.where(cont, False, self.clutch)
        self.running = np.where(cont, False, self.running)
        if np.any(half):
            self.qtr = np.where(half, 3, self.qtr)
            self.clock = np.where(half, 900.0, self.clock)
            self.clutch = np.where(half, False, self.clutch)
            self.to_h = np.where(half, 3, self.to_h)
            self.to_a = np.where(half, 3, self.to_a)
            self.poss = np.where(half, 1 - self.recv0, self.poss)
            self.running = np.where(half, False, self.running)
        tied = reg & (self.home == self.away)
        self.alive &= ~reg | tied
        if np.any(tied):
            self._start_ot(tied)
        self.alive &= ~ot

    def enter_clutch(self, mask: np.ndarray) -> None:
        self.clutch |= mask
        self.down = np.where(mask, 1, self.down)
        self.dist = np.where(mask, 10.0, self.dist)
        self.yl = np.where(mask, 75.0, self.yl)
        self.running = np.where(mask, False, self.running)

    def play(self, mask: np.ndarray) -> None:
        if not np.any(mask):
            return
        diff = self._diff()
        # Kneel only to finish a lead. One rule, not a menu.
        # A lead inside two minutes is knelt out, including the last down if the clock dies on it.
        kneel = (
            mask
            & (diff > 0)
            & (self.qtr == 4)
            & (self.clock <= 120)
            & ((self.down <= 3) | (self.clock <= 45))
        )
        take_fg = mask & ~kneel & (self.qtr == 4) & (diff == 0) & (self.yl <= 45) & (self.down >= 2)
        fourth = mask & (self.down == 4) & ~kneel & ~take_fg
        yb = np.where(self.yl <= 15, 0, np.where(self.yl <= 40, 1, 2))
        db = (self.dist > 3).astype(np.int8)
        cell = FOURTH[yb, db]
        u = self.rng.random((self.G, self.S))
        go = fourth & (u < cell[..., 0])
        fg = take_fg | (fourth & ~go & (u < cell[..., 0] + cell[..., 1]))
        punt = fourth & ~go & ~fg
        scrim = mask & ~kneel & ~fg & ~punt
        state = np.where(diff < 0, 0, np.where(diff > 0, 2, 1))
        p_pass = np.array([PASS_RATE["trail"], PASS_RATE["tie"], PASS_RATE["lead"]])[state]
        is_pass = scrim & (self.rng.random((self.G, self.S)) < p_pass)
        is_run = scrim & ~is_pass
        self._resolve_run(is_run)
        self._resolve_pass(is_pass)
        self._resolve_fg(fg)
        self._resolve_punt(punt)
        self._resolve_kneel(kneel)
        self._charge(mask, is_pass, is_run, kneel, fg | punt)

    def _talent(self) -> np.ndarray:
        return (
            self.m.td_logit[np.arange(self.G)[:, None], self.poss]
            + self.shock[np.arange(self.G)[:, None], np.arange(self.S)[None, :], self.poss]
        )

    def _trailing_late(self) -> np.ndarray:
        diff = self._diff()
        return (diff < 0) & (self.qtr == 4) & (self.clock <= 120)

    def _resolve_run(self, mask: np.ndarray) -> None:
        if not np.any(mask):
            return
        mean = np.where(self._trailing_late(), 2.2, RUN_MEAN + 0.6 * self._talent())
        yards = self.rng.normal(mean, RUN_SD)
        self._advance(mask, yards, stop=self.rng.random((self.G, self.S)) < 0.08)

    def _resolve_pass(self, mask: np.ndarray) -> None:
        if not np.any(mask):
            return
        talent = self._talent()
        pc = 1 / (1 + np.exp(-(_logit(COMP) + 0.35 * talent)))
        u = self.rng.random((self.G, self.S))
        comp = mask & (u < pc)
        sack = mask & ~comp & (u < pc + SACK)
        inter = mask & ~comp & ~sack & (u < pc + SACK + INT)
        inc = mask & ~comp & ~sack & ~inter
        yards = self.rng.normal(np.where(self._trailing_late(), 6.0, COMP_MEAN + talent), COMP_SD)
        self._advance(comp, yards, stop=self.rng.random((self.G, self.S)) < 0.22)
        self._advance(sack, self.rng.normal(-6.0, 2.0), stop=np.zeros((self.G, self.S), bool))
        self._turnover(inter, np.full((self.G, self.S), 55.0))
        self.down = np.where(inc, self.down + 1, self.down)
        fail = inc & (self.down >= 5)
        self._turnover(fail, np.clip(100 - self.yl, 1, 99))
        self.running = np.where(inc, False, self.running)

    def _advance(self, mask: np.ndarray, yards: np.ndarray, stop: np.ndarray) -> None:
        new_yl = self.yl - yards
        td = mask & (new_yl <= 0)
        safety = mask & (new_yl >= 100)
        made = mask & ~td & ~safety & (yards >= self.dist)
        short = mask & ~td & ~safety & ~made
        self._add(self._td_points(td), td, self.poss == 0)
        self.poss = np.where(td | safety, 1 - self.poss, self.poss)
        self.yl = np.where(td, 75.0, self.yl)
        self.down = np.where(td, 1, self.down)
        self.dist = np.where(td, 10.0, self.dist)
        # Safety: two points for the defence, then the team that gave it up receives.
        self.home += np.where(safety & (self.poss == 0), 2, 0).astype(np.int16)
        self.away += np.where(safety & (self.poss == 1), 2, 0).astype(np.int16)
        self.yl = np.where(safety, 65.0, self.yl)
        self.down = np.where(safety, 1, self.down)
        self.yl = np.where(made | short, np.clip(new_yl, 1, 99), self.yl)
        self.down = np.where(made, 1, self.down)
        self.dist = np.where(made, np.minimum(10.0, self.yl), self.dist)
        self.down = np.where(short, self.down + 1, self.down)
        self.dist = np.where(short, np.maximum(1.0, self.dist - yards), self.dist)
        fail = short & (self.down >= 5)
        self._turnover(fail, np.clip(100 - self.yl, 1, 99))
        self.running = np.where(mask, ~(stop | td | safety | fail), self.running)
        self._maybe_ot_end(td, is_td=True)

    def _turnover(self, mask: np.ndarray, yl: np.ndarray) -> None:
        self.poss = np.where(mask, 1 - self.poss, self.poss)
        self.yl = np.where(mask, yl, self.yl)
        self.down = np.where(mask, 1, self.down)
        self.dist = np.where(mask, 10.0, self.dist)
        self.running = np.where(mask, False, self.running)

    def _resolve_fg(self, mask: np.ndarray) -> None:
        if not np.any(mask):
            return
        dist = self.yl + 17.0
        make = mask & (self.rng.random((self.G, self.S)) < _fg_make(dist))
        self._add(np.where(make, 3, 0).astype(np.int16), make, self.poss == 0)
        self.poss = np.where(make, 1 - self.poss, self.poss)
        self.yl = np.where(make, 75.0, self.yl)
        self.down = np.where(make, 1, self.down)
        miss = mask & ~make
        spot = np.where(self.yl <= 20, 80.0, np.clip(100 - self.yl, 1, 99))
        self._turnover(miss, spot)
        self.running = np.where(mask, False, self.running)
        self._maybe_ot_end(make, is_td=False)

    def _resolve_punt(self, mask: np.ndarray) -> None:
        recv = np.clip(self.rng.normal(72.0, 12.0), 40.0, 90.0)
        self._turnover(mask, recv)

    def _resolve_kneel(self, mask: np.ndarray) -> None:
        self.down = np.where(mask, self.down + 1, self.down)
        self.yl = np.where(mask, np.minimum(99.0, self.yl + 1), self.yl)
        self.running = np.where(mask, True, self.running)
        fail = mask & (self.down >= 5)
        self._turnover(fail, np.clip(100 - self.yl, 1, 99))

    def _charge(self, acted, is_pass, is_run, kneel, special) -> None:
        pace = np.where(self.running, 34.0, 6.0)
        pace = np.where(kneel, 38.0, pace)
        pace = np.where(special, 8.0, pace)
        cross = (
            acted
            & (self.qtr >= 2)
            & (self.clock > 120)
            & (self.clock - pace <= 120)
            & (self.qtr != 3)
        )
        pace = np.where(cross, np.maximum(self.clock - 120.0, 0.0), pace)
        pace = np.minimum(pace, np.maximum(self.clock, 0))
        self.clock = np.where(acted, self.clock - pace, self.clock)
        self.running = np.where(cross, False, self.running)
        self._end_quarter(acted & (self.clock <= 0) & ~cross)


def simulate(match: Matchup, n_sims: int = 4000, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Final scores, shape (G, n_sims). Same seed and matchup, same scores."""
    rng = np.random.default_rng(seed)
    st = _State(match, n_sims, rng)
    for _ in range(70):
        if not np.any(st.alive):
            break
        margin = np.abs(st.home - st.away)
        window = ((st.qtr == 4) & (st.clock <= CLUTCH_Q4) & (margin <= CLUTCH_MARGIN)) | (
            (st.qtr == 2) & (st.clock <= CLUTCH_Q2) & (margin <= CLUTCH_MARGIN)
        )
        st.enter_clutch(st.alive & window & ~st.clutch)
        st.drive(st.alive & ~st.clutch)
        st.play(st.alive & st.clutch)
    return st.home.astype(np.int64), st.away.astype(np.int64)


def split_probs(home: np.ndarray, away: np.ndarray) -> dict[str, np.ndarray]:
    """Win probabilities that sum to 1, with a tie counted half each."""
    hw = (home > away).mean(axis=1)
    aw = (away > home).mean(axis=1)
    tw = (home == away).mean(axis=1)
    return {
        "p_home": hw + 0.5 * tw,
        "p_away": aw + 0.5 * tw,
        "p_tie": tw,
        "margin": (home - away).mean(axis=1),
        "total": (home + away).mean(axis=1),
    }
