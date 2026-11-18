"""CI gate: the ensemble and the model-only stack must not get worse than the committed baseline.

Usage:
  python scripts/check_baseline.py                 # fast: re-stack the cached component predictions
  python scripts/check_baseline.py --ref origin/main   # compare against main's baseline (PRs)
  python scripts/check_baseline.py --full          # recompute components from nflverse data

The fast mode re-runs the strict walk-forward stacking from ``reports/baseline_components.parquet``
(a few seconds, no network) and fails if log loss or Brier of ``ens`` or ``model_only`` worsen
by more than the tolerance stored in the baseline. ``--full`` also regenerates Elo, Kalman and
LightGBM from the data in ``data/`` (run ``ensemblitz update`` first), so it catches changes in
features and models; the weekly workflow ``baseline-full.yml`` runs it.

If you changed the models on purpose, rerun ``ensemblitz baseline --full``, commit the new
baseline files and explain the change in the PR. When ``--ref`` is given the comparison is made
against the baseline on that ref, so regenerating the baseline cannot hide a regression.
Exit 1 on failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = "reports/baseline_2018_2025.json"
KEYS = ("model_only", "ens")


def load_baseline(ref: str | None) -> tuple[dict, str]:
    if ref:
        p = subprocess.run(
            ["git", "show", f"{ref}:{REL}"], cwd=ROOT, capture_output=True, text=True, check=False
        )
        if p.returncode == 0:
            return json.loads(p.stdout), f"{ref}:{REL}"
        print(f"aviso: {REL} no existe en {ref}; se usa el baseline del árbol de trabajo")
    return json.loads((ROOT / REL).read_text()), REL


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="recompute components from data/")
    ap.add_argument("--ref", default=None, help="git ref whose baseline is the reference")
    ap.add_argument("--tol-log-loss", type=float, default=None)
    ap.add_argument("--tol-brier", type=float, default=None)
    a = ap.parse_args()

    from ensemblitz import baseline as B

    base, src = load_baseline(a.ref)
    gate = base["gate"]
    tol_ll = a.tol_log_loss if a.tol_log_loss is not None else gate["tolerance_log_loss"]
    tol_br = a.tol_brier if a.tol_brier is not None else gate["tolerance_brier"]

    errors: list[str] = []
    cache = B.load_cache()
    if a.full:
        import numpy as np

        fresh = B.components_from_pipeline()
        m = cache.merge(fresh, on="game_id", suffixes=("_c", "_f"))
        diffs = [
            float(np.nanmax(np.abs(m[f"{c}_c"] - m[f"{c}_f"])))
            for c in cache.columns
            if c.endswith(("_prob", "_margin"))
        ]
        worst = max(diffs) if diffs else 0.0
        print(f"componentes recomputados vs caché: diferencia máxima {worst:.2e}")
        if len(m) != len(cache) or worst > 1e-3:
            errors.append(
                "la caché de componentes no coincide con el recálculo desde los datos; "
                "ejecuta `ensemblitz baseline --full` y revisa por qué cambió"
            )
        new = B.gate_metrics(fresh)
    else:
        new = B.gate_metrics(cache)

    print(f"referencia: {src}  ({gate['n_games']} partidos; ahora {new['n_games']})")
    print(f"{'fuente':<11}{'métrica':<10}{'base':>9}{'ahora':>9}{'delta':>9}{'tope':>8}")
    for k in KEYS:
        for metric, tol in (("log_loss", tol_ll), ("brier", tol_br)):
            b, n = gate[k][metric], new[k][metric]
            bad = n - b > tol
            print(
                f"{k:<11}{metric:<10}{b:9.4f}{n:9.4f}{n - b:+9.4f}{tol:8.4f}{'  FALLA' if bad else ''}"
            )
            if bad:
                errors.append(f"{k} {metric}: {n:.4f} frente a {b:.4f} (tolerancia {tol})")
    mk = new["market"]["log_loss"] - gate["market"]["log_loss"]
    if abs(mk) > 1e-4:
        print(
            f"aviso: el log loss del mercado cambió {mk:+.5f}: datos o caché distintos del baseline"
        )
    if new["n_games"] != gate["n_games"]:
        print("aviso: el número de partidos evaluados cambió respecto al baseline")

    if errors:
        print("\nBARRERA DE BASELINE: FALLA", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("\nbarrera de baseline: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
