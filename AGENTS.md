# Instrucciones para agentes

## Estilo y diseño

- Idioma de la web, informes y commits de contenido: español de España. Horas en Europe/Madrid, cifras con coma decimal, °C y km/h.
- Diseño: seguir `DESIGN.md`. No cambiar tokens, fuentes ni la dirección visual sin que Jesús lo apruebe.
- Antislop: reglas en `.cursor/rules/antislop.mdc` y copia MIT en `third_party/antislop/` (conservar `LICENSE`). Sin raya larga (em dash) en texto escrito ni en la salida de la web.
- Nunca mostrar en la web rutas del repositorio, claves internas de casas de apuestas, ni cifras imputadas como si fueran datos reales.
- Una cifra derivada se calcula con los mismos valores que se muestran. La brecha entre dos porcentajes de la web es la resta de los dos enteros impresos (`gap_pp` en `site/build.py`), no la resta de los valores sin redondear.

## Ramas y pull requests

- No se toca `main` directamente. Cada cambio va en una rama nueva (`feat/...`, `fix/...`) y se abre un pull request. No se fusiona sin que Jesús lo diga.
- Un PR, un tema. Descripción en español: qué cambia, por qué y qué comprobaciones se han pasado (con las cifras).

## Comprobaciones obligatorias antes de dar un cambio por hecho

Se pasan todas, en este orden, y se pega el resultado en el PR. Si una falla, se arregla la causa; no se desactiva la comprobación ni se ensancha su tolerancia para que pase.

```bash
ruff check . && ruff format --check .
pytest -q
ensemblitz site && python scripts/check_site.py
python scripts/validate_outputs.py --site site/_build
python scripts/check_baseline.py            # en un PR: añade --ref origin/main
```

`make check` las encadena. `python scripts/check_baseline.py` re-apila en segundos las predicciones de la caché y falla si el log loss o el Brier del ensemble o del modelo sin mercado empeoran más de la tolerancia (0,0015 y 0,0007) frente al baseline. Si el cambio toca features, Kalman, LightGBM o datos, pasa además `ensemblitz update && python scripts/check_baseline.py --full`, que recalcula todo desde nflverse (es lo que hace el workflow semanal `baseline-full.yml`).

Un cambio de modelo que mejora el baseline se acepta regenerando los artefactos (`ensemblitz baseline --full`) y explicando la mejora en el PR con su intervalo de confianza. Un cambio que lo empeora no se fusiona salvo decisión explícita de Jesús.

## Sin fugas de información (regla dura)

- Todo lo que se use para predecir un partido sale de partidos y datos **anteriores** a su semana. Ratings, Elo, Kalman, LightGBM, pesos del ensemble, impacto por jugador y estatus de lesiones: walk-forward estricto, reajustando antes de cada (temporada, semana).
- Los hiperparámetros se ajustan solo con temporadas pasadas. Nada se elige mirando 2018 a 2025 y luego se evalúa en 2018 a 2025.
- Lesiones: usar el estatus del parte (`report_status`, `practice_status`), nunca la lista final de inactivos ni el rendimiento del jugador en la propia semana o después. Un valor por jugador se calcula solo con semanas previas.
- Todo código nuevo que ajuste algo con resultados lleva un test que cambia resultados y entradas de la semana W en adelante y comprueba que ninguna predicción de semanas anteriores se mueve (ver `tests/test_baseline.py` y `tests/test_features_leakage.py`).
- Los picks se congelan antes del kickoff y no se reescriben.

## Verifica tu trabajo

- No des algo por funcionando porque el código parece correcto: ejecútalo y mira la salida. Cada cambio de comportamiento lleva su test; cada cifra de un informe sale de un comando, no de la memoria.
- Antes de afirmar que un modelo mejora, compara con la línea base (`reports/BASELINE.md`) con intervalo de confianza. Con unos 2.000 partidos, diferencias de 0,002 de log loss son ruido.
- Cuando una comprobación nueva debería fallar, demuéstralo una vez (rómpelo a propósito y mira que se pone rojo) antes de fiarte de ella.
- Salidas JSON sin `NaN` (usar `null`). `validate_outputs.py` lo comprueba.
- Cuota y coste: no lances trabajos largos o en paralelo sin necesidad. Primero el check barato (`pytest -q`, `check_baseline.py` en modo rápido), después el caro.

## Fase 1 (lesiones)

- La regla para conectar algo a producción es el intervalo de confianza pareado del log loss frente a la variante sin el cambio: solo si el IC 95 % queda por debajo de cero. Una mejora de frontera se documenta y no se conecta. Resultado actual en `reports/PHASE1.md` (lesiones: no concluyente, sin conectar).
- Las variantes que se prueban después de ver los resultados se marcan como exploratorias y no deciden.

## Mapa útil

- `src/ensemblitz/baseline.py` y `baseline_report.py`: auditoría de la Fase 0. `ensemblitz baseline [--full]` regenera `reports/baseline_*.json|png`, `reports/BASELINE.md` y `reports/baseline_components.parquet`.
- `scripts/audit_injuries.py`: auditoría de los partes de lesiones de nflverse (necesita red); resultado en `reports/injury_audit.json`.
- `src/ensemblitz/impact.py`, `margin.py`, `phase1.py`, `phase1_report.py`: impacto de lesiones por jugador (valor sobre reemplazo, probabilidad de jugar, tabla discreta de márgenes). `ensemblitz phase1 [--full]` regenera `reports/phase1_*` y `reports/PHASE1.md`. Sin conectar a producción.
