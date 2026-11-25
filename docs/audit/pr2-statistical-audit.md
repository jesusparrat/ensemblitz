# PR2 Statistical Audit

**Estado: CI verificada.** Generado el **25 de noviembre de 2026, 23:46:51 UTC**, con el modelo `0.1.0`.

El informe completo, incluido el JSON con folds y métricas por temporada, se generó offline en CI y se adjunta como artefacto. Este documento conserva los resultados principales y las conclusiones.

- Ejecución CI: [run 45723813488](https://github.com/jesusparrat/ensemblitz/actions/runs/45723813488)
- Artefacto: `pr2-statistical-audit`
- Regeneración local: `uv run python scripts/audit_pr2.py`
- Sin descargas nflverse ni llamadas a The Odds API.

## 1. Población: 2.141 frente a 2.133

La discrepancia queda reconciliada:

| Concepto | N |
|---|---:|
| Partidos regulares jugados | 2.141 |
| Con predicciones válidas para todas las fuentes | 2.141 |
| Empates excluidos del scoring | 8 |
| Predicciones ausentes | 0 |
| Probabilidades inválidas | 0 |
| **Muestra final común** | **2.133** |

Los ocho excluidos son empates, no datos ausentes:

- `2018_01_PIT_CLE`
- `2018_02_MIN_GB`
- `2019_01_DET_ARI`
- `2020_03_CIN_PHI`
- `2021_10_DET_PIT`
- `2022_01_IND_HOU`
- `2022_13_WAS_NYG`
- `2025_04_GB_DAL`

Las tres fuentes comparten exactamente los mismos 2.133 partidos. SHA-256 de los IDs ordenados: `6c02e4792fce8c947492fc0d0e9db839b830b12f5cc712655ec55bc4d99cd144`.

## 2. Resultado global: modelo, mercado y ensemble

| Fuente | Accuracy | Brier | Log loss | Pendiente de calibración |
|---|---:|---:|---:|---:|
| MODEL_ONLY | 64,79 % | 0,22168 | 0,63440 | 0,928 |
| MARKET | **66,43 %** | **0,21108** | **0,60968** | 1,056 |
| ENSEMBLE | 66,24 % | 0,21165 | 0,61125 | 0,991 |

### Diferencias emparejadas frente al mercado

Bootstrap por temporadas completas, 10.000 réplicas, semilla 20260, IC percentil del 95 %. La diferencia es fuente menos MARKET; valores positivos en Brier y log loss indican peor resultado.

| Fuente | Δ Log loss | IC 95 % | Δ Brier | IC 95 % |
|---|---:|---:|---:|---:|
| MODEL_ONLY | +0,02472 | [+0,02149; +0,02755] | +0,01059 | [+0,00952; +0,01166] |
| ENSEMBLE | +0,00157 | [+0,00047; +0,00266] | +0,00057 | [+0,00008; +0,00108] |

**Conclusión estadística:** el mercado supera claramente a MODEL_ONLY. También supera al ensemble publicado en Brier y log loss; la diferencia es pequeña, pero los dos intervalos emparejados quedan por encima de cero. La proporción de réplicas en que ENSEMBLE mejora el log loss de MARKET es 0,22 %.

Esto no implica que el modelo carezca de valor explicativo o editorial, pero sí que el backtest actual no demuestra una mejora predictiva sobre el mercado.

## 3. Calibración de favoritos de al menos el 75 %

Cada fuente se evalúa en su propio subconjunto de favoritos; los tamaños, por tanto, no son iguales.

| Fuente | N | Probabilidad media | Acierto real | Sobreconfianza | IC 95 % de la brecha |
|---|---:|---:|---:|---:|---:|
| MODEL_ONLY | 396 | 80,86 % | 76,52 % | **+4,35 pp** | [+0,86; +7,77] pp |
| MARKET | 470 | 80,93 % | 82,34 % | −1,41 pp | [−4,63; +1,57] pp |
| ENSEMBLE | 525 | 81,31 % | 80,57 % | +0,74 pp | [−2,18; +3,85] pp |

La hipótesis de +4,3 puntos de sobreconfianza queda reproducida para MODEL_ONLY, con un intervalo que no cruza cero. No se reproduce para el ensemble publicado: su sobreconfianza es de 0,74 pp y el intervalo incluye cero.

En los mismos 525 partidos donde el ensemble asigna al favorito al menos un 75 %, el acierto real es 80,57 % (IC por temporadas: 77,61–83,19 %). En esos mismos partidos, MODEL_ONLY asigna de media 76,82 % al favorito del ensemble, MARKET 80,08 % y ENSEMBLE 81,31 %. Esta distinción evita confundir el subconjunto de favoritos propios de cada fuente con una comparación sobre los mismos partidos.

## 4. Pesos del ensemble y alternativas restringidas

- La suma de pesos del ensemble publicado supera 1 en el **100 % de los folds**; media 1,091, rango 1,032–1,240.
- MODEL_ONLY supera 1 en el 97,22 % de los folds; media 1,074.
- Las variantes con suma de pesos restringida (`ens_cap1`, `ens_pool`) mejoran ligeramente los puntos estimados, pero sus intervalos emparejados frente al ensemble cruzan cero tanto en log loss como en Brier.

**Decisión:** no cambiar pesos ni hiperparámetros en PR2. Los resultados no justifican retuning en esta fase. La suma de pesos superior a uno se documenta como diagnóstico, no como prueba automática de mala calibración.

## 5. ATS de MODEL_ONLY

- 1.024 victorias, 1.057 derrotas y 52 pushes.
- Porcentaje de acierto: 49,21 % (IC 95 %: 47,06–51,35 %).
- Contraste frente al break-even del 52,38 %: (p=0,0040).

No aparece una ventaja ATS en esta muestra. No debe presentarse como señal de valor esperado o rentabilidad.

## 6. Auditoría de fuga temporal

**Sin fuga de resultados identificada en la secuencia walk-forward examinada:**

- Elo y ajustes por rival: las features de una semana se calculan antes de actualizar el estado con los resultados de esa misma semana.
- Kalman: `run_kf` predice la semana completa antes de actualizarla. `kalman.tune` limita la optimización a temporadas estrictamente anteriores a `before_season`; se añadió una regresión que comprueba ese corte.
- LightGBM: `pipeline._train_mask` usa únicamente partidos jugados de temporadas/semanas anteriores; se añadió un test directo del límite.
- El stack se vuelve a ajustar antes de cada semana con predicciones de componentes fuera de muestra.

**Riesgos no resueltos ni cuantificados:**

1. `home_qb_id`/`away_qb_id`, `temp` y `wind` alimentan features, pero el histórico no conserva snapshots ni timestamps que prueben cuándo se conocieron. La identidad real del QB y el tiempo observado pueden no coincidir con lo que era conocible al pronosticar. Es un riesgo potencial de disponibilidad, no una fuga de resultados demostrada.
2. `models/kf_params.json` no registra el periodo de entrenamiento de cada parámetro. El código de tuning respeta el corte, pero no se puede demostrar que todos los valores versionados se generaran así.
3. No hay historial reproducible de selección manual de features/hiperparámetros de LightGBM; no se puede demostrar que las decisiones históricas fueran independientes de temporadas futuras.
4. El snapshot de datos hashea `data/raw/*.parquet`, pero las features también leen `data/processed/team_games.parquet` y `qb_games.parquet`, que no se hashean directamente.
5. Las lesiones usan recuentos de semanas t−1/t−2, no el informe de la semana actual; los timestamps históricos de publicación no se conservan.

No se han cambiado parámetros ni reentrenado modelos para ocultar estos riesgos. Cuantificarlos requiere datos point-in-time y una evaluación controlada posterior.

## 7. Fuentes de mercado: discrepancia IND–HOU

Para IND @ HOU, semana 11 de 2026:

- nflverse: probabilidad local sin margen **84,00 %**, calculada con moneylines −700 / +500.
- The Odds API: media no ponderada de probabilidades Shin sin margen **85,77 %**, con 42 operadores.
- La media multiplicativa archivada antes de la limpieza era **84,07 %**.
- Captura de The Odds API: 17 nov 2026, 20:54:38 UTC.
- Predicción: 17 nov 2026, 22:07:57 UTC.
- Kickoff: 20 nov 2026, 01:15:00 UTC.

La diferencia 86 % frente a 84 % procede de fuentes y métodos de de-vig distintos, no de un cambio de signo. La captura de The Odds API precede a la generación de la predicción en 1 h 13 min 19 s. Ninguno de estos valores es una cuota de cierre. El histórico de backtest usa las líneas de cierre nflverse; la captura de The Odds API es otra observación pre-kickoff.

El consenso Shin almacenado es la media aritmética no ponderada de probabilidades Shin por operador, no un cálculo Shin sobre un mercado agregado.

## 8. Noticias, cuotas y convención de margen

- `apply_news` modifica solo probabilidad y margen del ensemble. El titular MODEL_ONLY permanece intacto; v1 registra `news_adjustment.applies_to = "ensemble"`. No hay archivo histórico point-in-time para incluir noticias en el backtest.
- Se eliminaron de los informes actuales `reports/odds/` los precios individuales, nombres de operadores, mejores precios, EV y edge frente al ensemble. Solo se conservan probabilidad agregada media-Shin, timestamp y número de operadores. Los snapshots históricos congelados no se reescribieron.
- Los términos públicos de The Odds API permiten datos derivados en interfaces de usuario siempre que los datos no sean el producto principal vendido o redistribuido, y prohíben redistribuir un feed raw independiente ([términos](https://the-odds-api.com/terms-and-conditions.html)). Esto no sustituye la revisión de un acuerdo específico de cuenta.
- Convención canónica: margen = puntos local − visitante. En nflverse, `spread_line > 0` indica favorito local. The Odds API usa el signo contrario para `point`; se convierte con `odds_api_margin_home(point) = -point`. Los tests cubren la conversión y el fallback de spread nflverse.

## 9. Validación CI

<badge color="success">Todo correcto</badge>

- `uv lock --check`
- `uv sync --frozen --extra dev`
- `ruff check .`
- `ruff format --check .`
- **160 tests passed**
- Build del site y validación HTML
- `validate_outputs.py`
- `verify_integrity.py`
- Baseline gate: 2.133 partidos antes y después; OK
- Auditoría PR2 offline: OK
- Artefacto de informe completo subido correctamente

## 10. Límites y decisiones

El bootstrap conserva la dependencia dentro de cada temporada, pero solo hay ocho clusters independientes; los intervalos son informativos y deben interpretarse con cautela. No se han retuneado pesos ni hiperparámetros, no se han reescrito snapshots, no se han realizado llamadas a The Odds API y no se ha modificado HTML/UI. `AGENTS.md` ya estaba en inglés; no requería migración.
