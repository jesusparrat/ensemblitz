# DESIGN.md, ensemblitz

Status: PR 4 visual identity approved by Jesús. Editorial sports-data panel on neutral cool grey (`#F3F4F6`), two self-hosted typefaces (`Archivo` and `IBM Plex Mono`), full-bleed hero band without eyebrow kickers, and a left vertical yellow signal bar for market disagreement. Implemented in `src/ensemblitz/site/`. Any change of visual direction requires Jesús's approval (antislop R-37). Agent rules live in `AGENTS.md` and `.cursor/rules/antislop.mdc`.

## 1. Design direction

An NFL forecast panel read on desktop and phone, combining the sobriety of an editorial stat sheet with clear hierarchy. Dial: **ENERGY 3 / RHYTHM 3 / MOTION 2**.

- **Hard rules (enforced in CI by `scripts/check_site.py`):**
  - **Max 2 font families:** `Archivo` (editorial headlines, UI, prose) and `IBM Plex Mono` (all data figures, probabilities, summary readouts, dates). No `Doto`, no `Arial`, no third family.
  - **Max 3 body text sizes:** `13px` (metadata, table cells, captions, SVG labels), `15px` (body copy, controls, facts, navigation), `17px` (hero lede and subheads). Display headlines (`34px` to `136px` in condensed `Archivo`) and featured data readouts (`36px` to `44px` in `IBM Plex Mono`) are documented separately as display/readout roles.
  - **Minimum 13 px everywhere:** zero visible text below `13px`, including table sort indicators, tags, mobile labels, and SVG chart labels.
  - **No pills:** no capsule badges or `border-radius` above `2px` (`--r-s`).
  - **No eyebrow kickers:** no `<small>` kicker stacked above `<h1>`. Context such as season or week sits naturally in the lead copy below `<h1>`.
  - **No nested cards:** game rows sit directly on dotted rules; flagged games lift onto `--surface` with a `4px` left vertical yellow bar rather than boxes inside boxes.
  - **No beige and no purple:** neutral cool grey paper (`#F3F4F6`) and slate dark mode (`#0E1014`).
  - **No official NFL logos or derivatives.**

## 2. Typography (self-hosted SIL OFL 1.1 woff2, no CDN)

| Role | Font | Sizes | Use |
|---|---|---|---|
| Display headlines | **Archivo** (variable, `wdth 62`, `wght 800`) | `34px`, `40px`, `clamp(56px..136px)` | Hero `<h1>`, day/section `<h2>`, card matchup `<h3>` |
| Body and UI | **Archivo** (`wdth 100`, `wght 400-700`) | `13px`, `15px`, `17px` | Metadata/captions (`13px`), prose/controls (`15px`), lede (`17px`) |
| Featured readouts | **IBM Plex Mono** (`wght 600`, tabular) | `36px`, `44px` | Hero summary counters and card win probability |
| Inline figures | **IBM Plex Mono** (`wght 400-600`, tabular) | `13px`, `15px`, `17px` | Kickoff times, points, ranges, margins, totals, table cells, dates |

## 3. Colour (3 neutrals + 1 signal accent)

WCAG 2.x contrast is enforced in CI by `scripts/check_site.py`.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` | `#F3F4F6` | `#0E1014` | Page background (cool neutral grey) |
| `--surface` | `#FFFFFF` | `#161920` | Full-bleed hero band, top bar, flagged game row, table highlight |
| `--ink` | `#111318` | `#F3F4F6` | Primary text, headlines, probability bar fill, strong rules |
| `--ink-2` | `#4B5260` | `#A7AFBE` | Secondary text, ledes, captions, table headers |
| `--ink-3` | `#5C6473` | `#8C95A6` | Minimal metadata, dotted dividers |
| `--rule` | `#D4D8DF` | `#282D38` | Hairline borders, SVG gridlines |
| `--cell-off` | `#CFD5DE` | `#2C323F` | Probability bar track (decorative) |
| `--bar-other` | `#9AA2B1` | `#4D5566` | Non-picked histogram bars |
| `--flag` | `#FFD60A` | `#FFD60A` | Left vertical market-disagreement signal bar (`4px` row/counter, `3px` inline) and logo accent |
| `--on-flag` | `#111318` | `#111318` | High-contrast ink pairing on yellow |

Rules:
- Yellow is never text on light backgrounds. On light mode it acts as a vertical signal rule beside high-contrast `--ink` text that carries the numeric value.
- No semantic green or red for sign differences: the explicit sign (`+` / `−`) and team abbreviation carry the meaning.
- Forbidden: gradients, glow, glassmorphism, beige, purple, or a second accent.

## 4. Layout, hero and components

- **Container:** `1240px` max width, `24px` gutter (`16px` at `<= 640px`).
- **Full-bleed hero (`.hero-band`):** sits outside `<main class="wrap">` on `--surface` with a bottom `1px` `--ink` rule; inner `.wrap.head` aligns cleanly with page content across `375`, `768`, `1280`, and `1440px`.
- **Spacing scale (px):** `4, 8, 12, 16, 24, 32, 48, 64`.
- **Game row:** time and weekday | `AWAY at HOME` in condensed `34px` with full team names | winner, probability in `36px` `IBM Plex Mono`, continuous bar with `50%` hairline, and market line | expected points per team with 80% range | positive winning margin (`HOU +8,7` / `HOU +8.7`) | total. Flagged rows (`>= 5` points from market) carry a `4px` left vertical `--flag` rule on `--surface` and inline `.sig` (`| +11 Market: 56%`) without repeating the difference.
- **Game page market block:** displays one market win probability with named source and explicit timestamp kind (fetched vs captured vs read), plus a visually separated `Reference line (nflverse)` block for literal spread (`HOU −12,5`) and total.
- **Mobile tables (`<= 640px`):** zero horizontal scroll site-wide. Narrow 2-to-4 column tables fit cleanly (`table.fit`); wide 5-to-7 column tables stack into `data-label` blocks (`table.stack`), keeping `table.sortable.stack thead` as a wrapping bar of `>= 44px` sort buttons.
- **Breakpoints:** `1100px`, `900px`, `640px`. Minimum touch target `44px`.

## 5. Motion (dial 2)

Honours `prefers-reduced-motion` (disabled). Sliding nav indicator (`280ms`), button press (`150ms`), static-first countdown. No loops, pulses, or parallax.

## 6. Copy and data conventions on screen

- No em dashes anywhere in text or generated assets.
- Team names are the official English names in both languages.
- Margin: always the predicted favourite with a positive winning margin (`HOU +8,7` / `HOU +8.7`) and an 80% range ordered away to home with team labels (`IND +10 a HOU +27` / `IND +10 to HOU +27`); the negative spread sign (`HOU −12,5`) is reserved exclusively for literal market betting-line quotes. Never a home margin without a name.
- Market gap: integer difference computed from the two displayed percentages (`FLAG_PP = 5` in `site/build.py`).
- Times: `Europe/Madrid` (24-hour clock) on `/es/`, `America/New_York` (12-hour AM/PM ET) on `/en/`, including header, cards, game page, record, and footer.
- Empty states: plain human text, zero repository paths, zero bookmaker prices or EV.

## 7. Delivery gate

`scripts/check_site.py` (contrast, `<= 2` font families, zero `< 13px` in CSS/SVG, zero pills/kickers, no beige/purple, em dashes, language parity, ET on `/en/`, no false closing labels, no duplicate flagged gap, reconciled 2,133/2,141 on Method) + Playwright checks at `375`, `768`, `1280`, and `1440px` in ES and EN.
