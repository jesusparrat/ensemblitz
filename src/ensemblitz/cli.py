"""Command line interface: ``ensemblitz update | backtest | predict | grade | odds``."""

from __future__ import annotations

import logging

import numpy as np
import typer

from ensemblitz import config as C

app = typer.Typer(add_completion=False, help="NFL game prediction.")


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def update(
    first: int = C.FIRST_SEASON, last: int = typer.Option(0, help="0 = current season")
) -> None:
    """Download nflverse data and rebuild the processed tables."""
    from ensemblitz.data import download, load

    download.update_all(first, last or None)
    load.build_processed()
    typer.echo("data updated")


@app.command()
def backtest(refit: bool = typer.Option(False, help="Re-tune Kalman hyper-parameters")) -> None:
    """Walk-forward backtest; writes reports/backtest.md and reports/backtest.json."""
    from ensemblitz import backtest as B
    from ensemblitz.odds.validation import validate

    reg, results = B.run(refit=refit)
    extra = validate(reg)
    results["closing_line_validation"] = extra["json"]
    B.write_report(results, extra["md"])
    typer.echo(f"backtest written to {C.REPORTS_DIR}")


@app.command()
def baseline(
    full: bool = typer.Option(False, help="Recompute components from nflverse data in data/"),
    boot: int = typer.Option(10_000, help="Bootstrap resamples"),
) -> None:
    """Phase 0 audit: model-only vs market vs ensemble, walk-forward 2018-2025."""
    from ensemblitz import baseline as B
    from ensemblitz import baseline_report as R

    if full:
        comps = B.components_from_pipeline()
        B.save_cache(comps)
    else:
        comps = B.load_cache()
    res, _ = B.audit(comps, boot)
    B.write_json(res)
    B.reliability_plot(res)
    R.write_markdown(res)
    typer.echo(f"baseline written to {C.REPORTS_DIR}")


@app.command()
def phase1(
    full: bool = typer.Option(False, help="Rebuild injury features from data/ (ensemblitz update)"),
    boot: int = typer.Option(10_000, help="Bootstrap resamples"),
) -> None:
    """Phase 1 audit: per-player injury impact, availability and discrete margin table."""
    import json

    from ensemblitz import baseline as B
    from ensemblitz import impact as I  # noqa: E741
    from ensemblitz import phase1 as P
    from ensemblitz import phase1_report as R

    if full:
        feats = P.build_injury_features()
        P.save_inputs(feats)
        d = I.load_inputs()
        rows = I.injury_rows(d["inj"], d["snaps"], d["ids"])
        av = P.availability_summary(rows, C.LAST_BACKTEST_SEASON + 1, 1)
        R.AVAIL_PATH.write_text(json.dumps(av, indent=1) + "\n")
    feats, hist = P.load_inputs_cached()
    res, _ = P.audit(B.load_cache(), feats, hist, boot)
    P.write_json(res)
    P.forest_plot(res)
    R.write_markdown(res)
    typer.echo(f"phase1 written to {C.REPORTS_DIR}; verdict: {res['verdict']['significant_at_95']}")


@app.command()
def predict(
    season: int = typer.Option(0, help="0 = current season"),
    week: int = typer.Option(0, help="0 = next unplayed week(s)"),
    weeks: int = typer.Option(1, help="How many upcoming weeks when --week is 0"),
    news: bool = typer.Option(True, help="Apply confirmed-out players from news/<season>/"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Write a new snapshot for a week that already has one (refused after first kickoff)",
    ),
    production: bool = typer.Option(
        False, "--production", help="Require a clean git tree and mark the snapshot reproducible"
    ),
) -> None:
    """Write a new immutable snapshot under predictions/<season>/weekXX/."""
    from ensemblitz.data.download import current_season
    from ensemblitz.predict import run_predict

    for p in run_predict(
        season or current_season(),
        week or None,
        weeks,
        news,
        force=force,
        production=production,
    ):
        typer.echo(f"wrote {p}")


@app.command()
def grade() -> None:
    """Grade frozen picks (only those generated before kickoff)."""
    from ensemblitz.grade import run_grade

    s = run_grade()
    typer.echo(f"graded {s['n_graded']} games")


@app.command()
def odds(
    season: int = typer.Option(0, help="0 = current season"),
    week: int = typer.Option(0, help="0 = next predicted week"),
    fetch: bool = typer.Option(True, help="Call The Odds API if ODDS_API_KEY is set"),
    report: bool = typer.Option(True, help="Write the comparison report (needs predictions)"),
) -> None:
    """Fetch sportsbook odds and/or compare them with our picks.

    Fetching does not need predictions, so the weekly job can run this before
    ``ensemblitz predict``. Without a key it skips politely. ``--no-report`` only
    refreshes the cache; ``--no-fetch`` writes the report from the cache.
    """
    from ensemblitz.data.download import current_season
    from ensemblitz.odds.report import run_odds

    msg = run_odds(season or current_season(), week or None, fetch=fetch, report=report)
    typer.echo(msg)


@app.command()
def pbp(
    evaluate: bool = typer.Option(
        False, "--evaluate", help="Walk-forward 2018-2025, write reports/PBP_SIM.md"
    ),
    sims: int = typer.Option(1000, help="Simulations per game"),
    home: str = typer.Option("", help="Home team abbreviation, with --away"),
    away: str = typer.Option("", help="Away team abbreviation, with --home"),
    season: int = typer.Option(0, help="Season for a single game (0 = latest backtest season)"),
    week: int = typer.Option(1, help="Week for a single game; rates use only earlier weeks"),
    seed: int = typer.Option(0, help="Random seed"),
) -> None:
    """Drive-level Monte Carlo with a clutch window. Not used by `ensemblitz predict`."""
    from ensemblitz.sim.drive_fit import load_drives, rates_before
    from ensemblitz.sim.hybrid import from_book, simulate, split_probs
    from ensemblitz.sim.pbp_eval import run_evaluation

    if evaluate:
        payload = run_evaluation(n_sims=sims, seed=seed or 202603)
        g = payload["gates"]
        typer.echo(
            f"log loss {g['win_prob_log_loss']:.4f}  model-only {g['model_only_log_loss']:.4f}  "
            f"margin sd {g['margin_sd']:.2f}  eligible {g['eligible_for_production']}"
        )
        typer.echo(f"wrote {C.REPORTS_DIR / 'PBP_SIM.md'}")
        return
    if not home or not away:
        raise typer.BadParameter("pass --evaluate, or both --home and --away")
    season = season or C.LAST_BACKTEST_SEASON
    book = rates_before(load_drives(), season, week)
    match = from_book(
        book,
        np.array([home.upper()]),
        np.array([away.upper()]),
        np.array([season]),
        is_neutral=False,
    )
    h, a = simulate(match, n_sims=sims, seed=seed)
    summary = split_probs(h, a)
    typer.echo(
        f"{away.upper()} @ {home.upper()} {season} week {week}: "
        f"home win {summary['p_home'][0]:.3f}  "
        f"margin {summary['margin'][0]:+.1f}  "
        f"total {summary['total'][0]:.1f}"
    )


@app.command()
def site(out: str = typer.Option("", help="Output directory (default site/_build)")) -> None:
    """Build the static website from predictions/, results/ and reports/."""
    from pathlib import Path

    from ensemblitz.site import build_site

    path = build_site(out=Path(out) if out else None)
    typer.echo(f"site written to {path}")


if __name__ == "__main__":
    app()
