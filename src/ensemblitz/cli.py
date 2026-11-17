"""Command line interface: ``ensemblitz update | backtest | predict | grade | odds``."""

from __future__ import annotations

import logging

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
def predict(
    season: int = typer.Option(0, help="0 = current season"),
    week: int = typer.Option(0, help="0 = next unplayed week(s)"),
    weeks: int = typer.Option(1, help="How many upcoming weeks when --week is 0"),
) -> None:
    """Write frozen predictions to predictions/<season>/weekXX.json."""
    from ensemblitz.data.download import current_season
    from ensemblitz.predict import run_predict

    for p in run_predict(season or current_season(), week or None, weeks):
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
) -> None:
    """Compare our picks with sportsbook odds (needs ODDS_API_KEY; skips politely without it)."""
    from ensemblitz.data.download import current_season
    from ensemblitz.odds.report import run_odds

    msg = run_odds(season or current_season(), week or None, fetch=fetch)
    typer.echo(msg)


if __name__ == "__main__":
    app()
