# DESIGN.md, ensemblitz

Status: visual direction approved by Jesús (grey paper, condensed Archivo, a single flag-yellow accent). Web v2 changes the structure, not the look: one clear card per game, in two languages. Implemented in `src/ensemblitz/site/`. Any change of visual direction is his call (antislop R-37). Agent rules are in `AGENTS.md` and `.cursor/rules/antislop.mdc`.

## 1. Design reading

A forecast panel for NFL fans who check on Sunday night (Madrid time), mostly from a phone, in the language of a **stadium scoreboard and a betting notepad**. Dial: **ENERGY 3 / RHYTHM 3 / MOTION 2**.

- ENERGY 3: week headline at up to 164 px in black condensed, dot-matrix numerals, one flag yellow that only appears where we differ from the market.
- RHYTHM 3: asymmetric 7/5 header, dense list grouped by day, two-column footnotes. No two sections share a composition.
- MOTION 2: a sliding navigation indicator, hover on rows, nothing in a loop.

Identity question: with the name removed it is still ensemblitz because of three things: dot-matrix numerals, extreme condensed headlines, and the yellow flag chip.

## 2. What web v2 changes and what it keeps

Keeps: near-black ink on light paper, one accent, table-like rows with thin rules, mono for figures, sober tone, Madrid times, dark mode, the typefaces and every colour token.

Changes (all from review feedback):
- **One number per question.** Each game answers, in this order: who wins and how likely, expected points per team with an 80% range, margin, total, one plain sentence of why. The market sits beside it as a reference.
- **The headline is the model on its own** (no market input). The market is shown as "Market: 66% (us +2)". The blended ensemble lives only in the technical detail of a game page, in history, and on the Method page.
- **The 20-cell bar is gone.** A single continuous bar fills to the winner's probability, with a hairline at 50%.
- **No exact score on the front page.** The example score appears only on the game page, labelled as an example.
- **No jargon on week pages**: no "ensemble", "pp", "sin comisión", simulation counts or "how to read the table". It all lives on the Method page and in its glossary.
- **No injury counts.** Only notable absences, per player, in points of value, labelled as context that is not part of any number.
- **No per-bookmaker prices, no expected value.** Only the consensus line.
- **Two languages.** Spanish at the root, English under `/en/`, a switch in the header that behaves like the theme toggle and is remembered.
- The "flags" section is gone. A flagged game gets a yellow chip on its own card, and the filter chips (All, Where we differ from the market) exist only when there is something to filter.

## 3. Typography (all free, SIL OFL 1.1, self-hosted woff2, no Google CDN)

| Role | Font | Why (R-06) |
|---|---|---|
| Headlines, teams, UI, text | **Archivo** (variable, wght 100-900, wdth 62-125) | Sports-heritage grotesque. The width axis gives one family with a condensed voice for headlines and team codes (wdth 62, weight 800) and normal width for text. Not one of the default list (Inter, Geist, Space Grotesk). |
| Table figures (points, %, margin, time) | **IBM Plex Mono** 400/500/600 | Tabular figures so columns align. Small figures only, never headlines. |
| Big readouts | **Doto** (variable, dot matrix) | The stadium board. One repeated voice: the win probability on a card and the figures in the header. |

Rules:
- Doto only at 32 px or more, digits only, always with a text equivalent (`aria-label`). Never in paragraphs.
- Headlines in sentence case, `letter-spacing` 0 to -0.01em. No tracked small caps.
- Scale (px): 12 (minimum, metadata only), 13, 15 (body), 18 (lede), 22, 28, 34 (card matchup), 40 (card probability), 44, 164 (week headline, `clamp(88px, 12.4vw, 164px)`).

## 4. Colour (cap R-29: 3 neutrals + 1 accent)

WCAG 2.x contrast is checked in CI by `scripts/check_site.py`, which reads the tokens from `site/static/style.css`.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` | #F4F4F2 | #0E0F11 | Background |
| `--surface` | #FFFFFF | #17181B | Cards and row hover |
| `--ink` | #101113 | #F2F2EF | Text, bar fill, strong rules |
| `--ink-2` | #50525A | #A6A8AF | Secondary text |
| `--ink-3` | #666870 | #8E9098 | Minimal metadata |
| `--rule` | #D5D5D0 | #2A2B30 | Decorative rules |
| `--cell-off` | #C9C9C3 | #2E2F34 | The track of the probability bar (decorative, the value is always text) |
| `--flag` | #FFD60A | #FFD60A | Disagreement with the market. Fill only, with `--on-flag` text on top |
| `--on-flag` | #101113 | #101113 | Text on yellow |

Rules:
- Yellow is never text on a light background (1.3:1). Always a fill with ink on top.
- No semantic green or red for the sign of a difference: the sign (+/−) and the number say it, so nothing depends on colour.
- Theme: light by default, `prefers-color-scheme` respected, manual button. Dark exists because games fall between 19:00 and 03:00 in Madrid.
- Forbidden: gradients, light orbs, glow, glass, a second accent.

## 5. Grid, spacing and shape

- Container 1240 px, gutter 24 px (16 px on mobile). Header in 12 columns, 7/5 split.
- Spacing: 4, 8, 12, 16, 24, 32, 48, 72, 112. The rhythm changes on purpose: 72 between big blocks, 48 before each day, 16 inside a row.
- Radii: 2 px on controls and chips, 6 px on cards. No pills.
- Rules: 1 px solid ink for day headers, 1 px dotted between rows. Dotted repeats the dot-matrix motif and is the only background "pattern".
- Breakpoints: 1100 (card layout), 900 (header to one column), 640 (phone). Touch targets 44 px minimum.

## 6. Components

**Game card** (desktop, six columns plus a sentence row): time and weekday | `AWAY en HOME` in condensed 34 px with full names under it | winner, probability in Doto, the continuous bar and the market line | expected points per team, one decimal, 80% range in brackets | margin as "HOU −8,7" | total. Under them, one sentence of why and, only if there are any, a line of notable absences. On phones it stacks: time and matchup, probability, points, margin and total, why.

**Why sentence**: a rule over the game's inputs, in this order: quarterback change, clear rest edge for the favourite, long trip against a home favourite, strong wind, home field in a close game, otherwise recent form. It is not a decomposition of the model and the Method page says so.

**Probability bar**: one filled bar, ink on the track colour, with a hairline at 50%. `aria-hidden`: the figure next to it carries the value.

**Market line**: "Market: 66% (us +2)". When the difference is 5 points or more, a yellow flag chip with the signed difference precedes it.

**Absences**: "Notable absences: Name (TEAM, out, 1,8 pts). Context: not included in the number." Per-player value in points of margin per game over a replacement; only Out or Doubtful players worth at least 1.0 point; never summed, never applied.

**Game page**: matchup headline; four readouts (win probability, margin, total, market probability); the points table with 80% ranges; "Against the market"; context list (rest, travel, QB, venue); notable absences; margin and total distribution charts; a collapsed "Technical detail" with every component. The example score is one sentence under the points table.

**History page**: the rules of the record, results by source (official pick, model alone, blended, market) on the same games, the game-by-game table with the pick type, and every saved week with its exact save time.

**Method page**: the only place for jargon: what the number is, how it is computed, the market and why no per-bookmaker prices, the why sentence, injuries, historical tables, calibration, limits and a glossary.

**Filters**: rectangular chips (All, Where we differ from the market) with counts, rendered only when at least one game is flagged. Active state is inverted ink. They work without reloading and the group is never empty.

**Language switch**: a 44 px bordered link in the header showing the other language ("EN" or "ES"), next to the theme button. A plain link to the twin page; the choice is saved in `localStorage` (`ens-lang`) and applied by `theme.js` before first paint, like `ens-theme`.

**Icons**: own 16 px set, 1.5 px stroke, square caps, one grid. Only those with meaning: flag, info. No sparkles, stars or bolts (R-04). No emoji.

**Navigation**: logo (5 bars, one taller and yellow, the flag) + condensed wordmark; links with a 3 px indicator that slides on hover and returns to the current page.

## 7. Motion (dial 2)

Everything honours `prefers-reduced-motion` (turned off).
- Navigation indicator: 280 ms, `cubic-bezier(.3,.7,.2,1)`.
- Chips and rows: 150 ms of colour and background, 1 px shift on press.
- Countdown to the next kickoff: text computed on load, no flicker.
- Forbidden: loops, pulses, parallax, delayed content, counters that climb from 0.

## 8. Content and copy (antislop-copywriting, R-02, R-17)

- No em dash in any text. Use a comma, a full stop, a colon or brackets.
- No filler lead-ins. A limitation is stated as a fact, on the Method page, not as a preamble.
- One sentence of context per game, always backed by a datum.
- Spanish: decimal comma, narrow no-break space before %, Madrid time with "(hora de Madrid)", °C and km/h. English: decimal point, no space before %. Weather only when `context.weather_known` is 1.
- Team names are the official English ones in both languages ("New York Giants", "Los Angeles Rams"). Headings use the abbreviation, sentences use the abbreviation too.
- The market comparison uses the integers as printed: 68% minus 66% is 2 points. Margin and total follow from the printed expected points.
- No figure without a source (R-17). Figures come from `predictions/`, `results/`, `reports/`.
- Footer: Madrid times, not UTC.

## 9. What not to do

- No gradients or light orbs.
- No grid or dot backgrounds as decoration (R-07). The only dotted element is the row rule.
- No default Geist/Inter/Space Grotesk, no JetBrains/Geist Mono (R-06).
- No bento, no three identical columns, no "how it works in 3 steps".
- No pills or capsules with a dot and glow; no badge above the headline.
- No Lucide or clones; no arrows on every button (R-08).
- No logo bar or invented testimonials; no unsourced figures (R-17).
- No accent in more than one place: yellow marks disagreement and the logo flag, nothing else.
- No "AI" language in the interface.
- No bookmaker prices, expected value or betting advice.

## 10. Delivery

Before calling anything done: `python scripts/check_site.py` (contrast, em dashes, language markers, jargon on week pages, bookmaker names, half-translated team names, empty filter groups), 390 px with no overflow, a visible 2 px focus ring in ink with a 3 px offset, `lang` on every page, `aria-label` on the probability readouts, the antislop Delivery Gate passed by whoever implements. Font files live in `site/static/fonts/` with their licences.

## 11. Data conventions on screen

- Margin: always the favourite and the points it gives, with a true minus sign and the language's decimal ("HOU −12,5"). Never a home margin without a name.
- Flags: |model alone minus market consensus| of 5 points or more, computed from the printed integers. The threshold is `FLAG_PP` in `site/build.py`.
- Times: always Europe/Madrid, also in the header and footer.
- Empty states: human text, no repository paths.
