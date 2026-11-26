# Backtest walk-forward

> **Artefacto anterior a PR2.** Este informe todavía no refleja la separación explícita MODEL_ONLY / MARKET / ENSEMBLE ni la reconciliación de población incorporadas al generador. La siguiente ejecución del backtest regenerará el informe con MODEL_ONLY separado. Para incertidumbre estadística (bloques de 2 semanas estratificados por temporada) usa `uv run python scripts/audit_pr2.py` o consulta `docs/audit/pr2-statistical-audit.md`.

Temporadas 2018–2025, 2141 partidos de temporada regular. Para cada semana, todo (ratings, Kalman, LightGBM, pesos del ensemble) se calcula solo con partidos anteriores. Generado: 2026-11-17T20:45:32+00:00.

## Global por modelo

| Modelo | Acierto | Brier | Log loss | MAE margen | ATS (G-P) | ATS % |
|---|---|---|---|---|---|---|
| Mercado (cierre) | 66.4% | 0.211 | 0.610 | 9.83 | — | — |
| Elo (MOV) | 63.2% | 0.223 | 0.638 | 10.23 | 1037-1052-52 | 49.6% |
| Kalman (fuerza dinámica) | 64.4% | 0.224 | 0.638 | 10.21 | 1039-1050-52 | 49.7% |
| LightGBM (sin mercado) | 65.0% | 0.222 | 0.634 | 10.24 | 1012-1077-52 | 48.4% |
| LightGBM (residuo vs mercado) | 66.5% | 0.213 | 0.614 | 9.98 | 1027-1062-52 | 49.2% |
| Simulador (params Kalman) | 64.3% | 0.224 | 0.638 | 10.21 | 1054-1035-52 | 50.5% |
| Ensemble | 66.2% | 0.212 | 0.611 | 9.83 | 899-925-48 | 49.3% |

MAE del total de puntos: ensemble 10.40, línea de total del mercado 10.40, Kalman 10.80.

## Por temporada (acierto / Brier / log loss / ATS%)

| Temporada | Mercado | Kalman | LightGBM | Ensemble |
|---|---|---|---|---|
| 2018 | 66.3% / 0.213 / 0.615 / — | 64.3% / 0.218 / 0.624 / 51.4% | 66.3% / 0.222 / 0.635 / 51.0% | 65.5% / 0.215 / 0.618 / 46.3% |
| 2019 | 63.7% / 0.215 / 0.619 / — | 64.1% / 0.226 / 0.645 / 49.2% | 62.5% / 0.227 / 0.644 / 46.4% | 63.7% / 0.217 / 0.623 / 46.6% |
| 2020 | 67.8% / 0.201 / 0.589 / — | 66.7% / 0.221 / 0.634 / 50.8% | 66.7% / 0.213 / 0.615 / 50.0% | 66.7% / 0.201 / 0.588 / 52.7% |
| 2021 | 62.4% / 0.217 / 0.622 / — | 62.7% / 0.231 / 0.656 / 50.4% | 63.8% / 0.223 / 0.637 / 51.9% | 62.4% / 0.217 / 0.624 / 50.4% |
| 2022 | 65.8% / 0.211 / 0.609 / — | 63.9% / 0.225 / 0.641 / 50.2% | 65.1% / 0.223 / 0.638 / 46.7% | 66.5% / 0.211 / 0.610 / 50.2% |
| 2023 | 68.4% / 0.219 / 0.627 / — | 61.8% / 0.230 / 0.651 / 49.2% | 65.1% / 0.229 / 0.650 / 46.1% | 67.6% / 0.219 / 0.629 / 46.1% |
| 2024 | 71.3% / 0.200 / 0.587 / — | 68.0% / 0.215 / 0.619 / 50.0% | 68.8% / 0.209 / 0.607 / 49.6% | 72.1% / 0.200 / 0.587 / 49.3% |
| 2025 | 65.7% / 0.212 / 0.609 / — | 63.8% / 0.223 / 0.635 / 46.9% | 62.0% / 0.227 / 0.645 / 45.8% | 65.3% / 0.213 / 0.611 / 50.5% |

## Calibración del ensemble

| Tramo | N | Prob. media | Acierto real |
|---|---|---|---|
| (-0.001, 0.1] | 5 | 8.8% | 20.0% |
| (0.1, 0.2] | 72 | 15.8% | 20.8% |
| (0.2, 0.3] | 187 | 25.4% | 20.9% |
| (0.3, 0.4] | 290 | 35.3% | 36.6% |
| (0.4, 0.5] | 284 | 44.4% | 44.4% |
| (0.5, 0.6] | 370 | 55.4% | 54.9% |
| (0.6, 0.7] | 382 | 64.6% | 60.5% |
| (0.7, 0.8] | 353 | 74.8% | 75.4% |
| (0.8, 0.9] | 168 | 84.6% | 85.1% |
| (0.9, 1.0] | 22 | 91.9% | 86.4% |

## ¿Le ganamos a la línea de cierre?

Para cada modelo, partidos donde su probabilidad difiere de la del mercado (sin margen) más de un umbral; se apuesta siempre el lado que el modelo prefiere con 1 unidad plana. `ATS` = contra el spread a −110 (se necesita 52,4 % para no perder). `ROI ML` = a la cuota de cierre real de moneyline (con comisión). `IC95` = intervalo de confianza del porcentaje. `Hit` = acierto directo del lado elegido frente a lo que el mercado esperaba de ese mismo lado.

| Modelo | Umbral | N | Hit (esperado mercado) | Log loss modelo / mercado | ATS | ATS % ±IC95 | ROI ATS −110 | ROI ML |
|---|---|---|---|---|---|---|---|---|
| Ensemble | todos | 2133 | 54.1% (54.8%) | 0.611 / 0.610 | 1018-1063 | 48.9% ±2.1 | -6.6% | -5.3% |
| Ensemble | >3 pp | 240 | 57.5% (59.0%) | 0.650 / 0.642 | 117-117 | 50.0% ±6.4 | -4.5% | -5.0% |
| Ensemble | >5 pp | 45 | 46.7% (53.7%) | 0.644 / 0.620 | 18-27 | 40.0% ±14.3 | -23.6% | -19.5% |
| Ensemble | >8 pp | 4 | 75.0% (52.1%) | 0.408 / 0.481 | 3-1 | 75.0% ±42.4 | +43.2% | +27.2% |
| LightGBM (residuo) | todos | 2133 | 45.4% (44.3%) | 0.614 / 0.610 | 1042-1039 | 50.1% ±2.1 | -4.4% | -1.9% |
| LightGBM (residuo) | >3 pp | 1247 | 43.3% (42.4%) | 0.630 / 0.621 | 618-599 | 50.8% ±2.8 | -3.1% | -0.8% |
| LightGBM (residuo) | >5 pp | 743 | 40.9% (41.2%) | 0.636 / 0.622 | 350-381 | 47.9% ±3.6 | -8.6% | -4.0% |
| LightGBM (residuo) | >8 pp | 288 | 41.3% (39.1%) | 0.651 / 0.636 | 148-135 | 52.3% ±5.8 | -0.2% | +1.8% |
| LightGBM (sin mercado) | todos | 2133 | 40.6% (42.2%) | 0.634 / 0.610 | 1012-1069 | 48.6% ±2.1 | -7.2% | -7.6% |
| LightGBM (sin mercado) | >3 pp | 1585 | 38.1% (40.2%) | 0.633 / 0.600 | 757-788 | 49.0% ±2.5 | -6.5% | -9.9% |
| LightGBM (sin mercado) | >5 pp | 1200 | 37.0% (39.1%) | 0.647 / 0.606 | 568-609 | 48.3% ±2.9 | -7.9% | -9.3% |
| LightGBM (sin mercado) | >8 pp | 758 | 36.1% (37.5%) | 0.650 / 0.597 | 368-379 | 49.3% ±3.6 | -6.0% | -9.1% |
| Kalman | todos | 2133 | 39.2% (40.5%) | 0.638 / 0.610 | 1040-1041 | 50.0% ±2.1 | -4.6% | -7.7% |
| Kalman | >3 pp | 1578 | 35.8% (38.2%) | 0.643 / 0.605 | 770-773 | 49.9% ±2.5 | -4.7% | -10.3% |
| Kalman | >5 pp | 1216 | 34.7% (36.4%) | 0.646 / 0.601 | 601-591 | 50.4% ±2.8 | -3.7% | -8.9% |
| Kalman | >8 pp | 774 | 32.8% (34.4%) | 0.658 / 0.597 | 391-368 | 51.5% ±3.6 | -1.7% | -7.9% |

**Conclusión:** en todos los partidos el ensemble tiene log loss 0.611 frente a 0.610 del mercado (+0.0016; menor es mejor); ningún modelo supera el punto de equilibrio de 52,4 % ATS con significancia (IC95 incluye o queda por debajo de él) y ninguno mejora al mercado en log loss de forma clara: **no hay evidencia de que le ganemos a la línea de cierre**. El valor de v0.1 está en las probabilidades calibradas y la distribución de marcadores, no en una ventaja contra el mercado.

ATS = contra el spread de cierre, apostando el lado que el modelo prefiere (G = ganadas, P = perdidas, empates = push). El ensemble coincide con el spread en muchos partidos (el mercado pesa casi todo), y ahí no hay apuesta, por eso su N es menor. El simulador usa los puntos esperados del Kalman y no entra en el ensemble.
