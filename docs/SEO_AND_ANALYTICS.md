# SEO, Open Graph Cards, and Opt-in Analytics

This document describes the static SEO metadata, social preview image pipeline, and optional analytics configuration built by `ensemblitz site`.

## 1. Base URL, Canonical Links, `sitemap.xml`, and `robots.txt`

The static site generator reads `SITE_BASE_URL` from the environment (default: `https://jesusparrat.github.io/ensemblitz`, trailing slash stripped). It must be an `http://` or `https://` URL.

Every rendered HTML page emits:

- `<link rel="canonical" href="...">` with an absolute URL (`/` for root `index.html`, `/en/` for `en/index.html`, and `/<relative-path>` for all other pages).
- `<link rel="alternate" hreflang="es|en|x-default" href="...">` pointing to the Spanish and English twins, with `x-default` mapped to the Spanish root URL.
- Open Graph (`og:site_name`, `og:locale`, `og:type`, `og:title`, `og:description`, `og:url`, absolute `og:image`, `og:image:width`, `og:image:height`, `og:image:alt`) and Twitter (`twitter:card=summary_large_image`, `twitter:title`, `twitter:description`, `twitter:image`) meta tags.

At the end of every build, `ensemblitz site` writes:

- `site/_build/sitemap.xml`: valid XML sitemap listing every rendered ES and EN HTML page with absolute `<loc>` URLs, bilingual `xhtml:link` alternates, and deterministic `<lastmod>` dates derived from the latest published snapshot timestamp.
- `site/_build/robots.txt`: allows indexing and declares `Sitemap: <SITE_BASE_URL>/sitemap.xml`.

## 2. Static Open Graph PNG Scope and Typography

Open Graph social preview images are generated deterministically at `1200x630` pixels by `src/ensemblitz/site/og.py` using `matplotlib` (already locked in `uv.lock`, zero new dependencies) and the `DESIGN.md` light-mode colour tokens (`#F3F4F6`, `#FFFFFF`, `#111318`, `#FFD60A`, `#4B5260`, `#5C6473`, `#D4D8DF`).

### Explicit card scope

- **Homepage:** `og/home-es.png` and `og/home-en.png` (always generated, including empty-site builds).
- **Published weekly pages:** `og/week-<season>-<ww>-es.png` and `og/week-<season>-<ww>-en.png` for every published `(season, week)` in `predictions/` (scales to full 18-week regular seasons and postseason weeks with no fixed week cap).
- **Fallback for other pages:**
  - Individual game pages reference their week's card (`og/week-<season>-<ww>-<lang>.png`).
  - Record (`/historial.html`, `/en/history.html`) and Method (`/metodo.html`, `/en/method.html`) pages reference the homepage card (`og/home-<lang>.png`).

### Font rendering note

The website's self-hosted web fonts under `src/ensemblitz/site/static/fonts/` are distributed as `.woff2` files (`Archivo` and `IBM Plex Mono`). Matplotlib's FreeType binding (`FT2Font`) cannot load `.woff2` directly, and `brotli` is intentionally not added to `uv.lock`.

`og.resolve_fonts()` verifies font files with `FT2Font` at runtime:

- If `.ttf` or `.otf` copies of `Archivo` and `IBM Plex Mono` are present in `src/ensemblitz/site/static/fonts/` and pass `FT2Font`, they are used.
- Otherwise, `og.py` deterministically renders cards with matplotlib's bundled TrueType fonts (`DejaVu Sans` for headings/body and `DejaVu Sans Mono` for numeric readouts) and records `used_web_fonts=False` with an explicit fallback reason. The code and documentation do not claim that `Archivo` or `IBM Plex Mono` are rendered in the PNGs while `.woff2`-only web fonts are in use.

## 3. Opt-in Privacy-Respecting Analytics (GoatCounter)

Analytics is **disabled by default**.

- Configuration variable: `ENSEMBLITZ_GOATCOUNTER_CODE` (wired in `.github/workflows/pages.yml` from repository variable `vars.GOATCOUNTER_CODE`, which expands to empty when unset).
- When `ENSEMBLITZ_GOATCOUNTER_CODE` is unset or empty:
  - Zero external `<script>` tags are emitted.
  - Zero analytics domains appear in the `Content-Security-Policy` meta tag (`script-src 'self'; connect-src 'none'`).
- When `ENSEMBLITZ_GOATCOUNTER_CODE` is explicitly set:
  - The code is validated strictly against `^[a-z0-9-]+$`; invalid values fail the build.
  - The build injects:
    ```html
    <script data-goatcounter="https://<code>.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
    ```
  - The CSP meta tag is extended **only** for `script-src` (`https://gc.zgo.at`) and `connect-src` (`https://<code>.goatcounter.com`).

### Data processing and privacy obligations

When enabled, GoatCounter does not set cookies or persistent cross-site identifiers. However, loading `count.js` and sending a hit to `https://<code>.goatcounter.com/count` causes the visitor's browser to transmit HTTP request metadata to a third-party processor, including:

- Requested page path and referrer header.
- Browser User-Agent, language, and viewport/screen dimensions.
- Client IP address (used transiently by GoatCounter to derive a rotating daily session hash for unique-visit counting).

**Zero cookies does not mean zero privacy or data-protection obligations.** Because request metadata (including IP address and User-Agent) is transmitted to an external processor when enabled, the site operator remains responsible for legal-basis assessment, processor terms, and visitor transparency notices (for example under the GDPR and Spain's LOPDGDD) before setting `GOATCOUNTER_CODE` in repository variables.
