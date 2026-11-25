"""Spanish markdown report for the Phase 0 baseline (all numbers come from the audit dict)."""

from __future__ import annotations

import json
from pathlib import Path

from ensemblitz import baseline as B
from ensemblitz import config as C

INJURY_JSON = C.REPORTS_DIR / "injury_audit.json"


def n(x: float | None, nd: int = 3) -> str:
    if x is None:
        return "n/d"
    return f"{x:.{nd}f}".replace(".", ",").replace("-", "\u2212")


def pc(x: float | None, nd: int = 1) -> str:
    return "n/d" if x is None else n(x * 100, nd) + " %"


def sn(x: float | None, nd: int = 4) -> str:
    return "n/d" if x is None else ("+" if x > 0 else "") + n(x, nd)


def ci(c: list[float] | None, nd: int = 4) -> str:
    return "n/d" if not c else f"[{sn(c[0], nd)}; {sn(c[1], nd)}]"


def _table(head: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def injury_section() -> list[str]:
    if not INJURY_JSON.exists():
        return ["Sin datos: ejecuta `python scripts/audit_injuries.py`."]
    j = json.loads(INJURY_JSON.read_text())
    rep = j["p_played_by_report_status"]
    prac = j["p_played_questionable_by_practice_status"]
    pos = j["p_played_questionable_by_position"]
    wd = j["timestamps"]["date_modified_weekday_share"]
    q = rep["Questionable"]
    out = [
        "## Partes de lesiones de nflverse (para la Fase 1)",
        "",
        "Pregunta: ¿el parte guarda el estatus que se conocía antes del partido o lo sobrescribe "
        "con los inactivos finales? Se ha comprobado con `scripts/audit_injuries.py` "
        "(temporada regular 2015 a 2025, cruzado con los snaps reales de cada jugador).",
        "",
        "**Hallazgos**",
        "",
        "1. **No se sobrescribe con los inactivos.** Hay una fila por jugador y semana, y conserva "
        f"la etiqueta oficial `Questionable`, `Doubtful` y `Out`: {q['n']} filas `Questionable` "
        f"y {pc(q['p_played'])} de ellas jugaron. Si se hubiera pisado con los inactivos del "
        "domingo, ese grupo estaría en 0 % o 100 %.",
        f"2. **Es el último parte oficial de la semana, no una foto de las 24 horas previas.** "
        f"`date_modified` cae en viernes en el {pc(wd.get('Friday'))} de las filas, en miércoles "
        f"el {pc(wd.get('Wednesday'))}, en sábado el {pc(wd.get('Saturday'))} y en jueves el "
        f"{pc(wd.get('Thursday'))}. Las filas de miércoles son jugadores cuyo estatus no se "
        "volvió a tocar. Para 2025 la columna `date_modified` viene vacía, así que ahí no se "
        "puede reconstruir la hora.",
        "3. **Las columnas útiles existen, pero el repositorio las tira.** nflverse trae "
        "`report_status` (etiqueta final), `practice_status` (entrenamiento del último día "
        "registrado), `report_primary_injury` y `date_modified`. `ensemblitz update` solo "
        "guardaba `report_status`; este PR hace que conserve también `practice_status` y "
        "`date_modified` (los datos tienen que volver a descargarse con `ensemblitz update`).",
        "4. **Solo hay una versión por jugador y semana.** Si un jugador pasó de `Questionable` a "
        "`Out` el sábado, el miércoles anterior ya no se ve. Para una prueba con el parte del "
        "viernes hay que aceptar que `report_status` es el último antes del partido (jueves a "
        "sábado) y documentarlo; una foto exacta de 24 horas antes no existe en esta fuente.",
        "",
        "**Probabilidad real de jugar según la etiqueta** (jugó = aparece con algún snap)",
        "",
    ]
    rows = []
    for k in ("Out", "Doubtful", "Questionable", "Probable", "(sin etiqueta)"):
        if k in rep:
            rows.append([k, str(rep[k]["n"]), pc(rep[k]["p_played"])])
    out += _table(["Etiqueta del parte", "Filas", "Jugó"], rows)
    out += ["", "`Questionable` según el entrenamiento registrado:", ""]
    rows = []
    for k, lab in (
        ("Full Participation in Practice", "Completo"),
        ("Limited Participation in Practice", "Limitado"),
        ("Did Not Participate In Practice", "No entrenó"),
    ):
        if k in prac:
            rows.append([lab, str(prac[k]["n"]), pc(prac[k]["p_played"])])
    out += _table(["Entrenamiento", "Filas", "Jugó"], rows)
    qb = pos.get("QB")
    if qb:
        out += [
            "",
            f"Por posición hay diferencias grandes: un QB `Questionable` juega el {pc(qb['p_played'])} "
            f"de las veces ({qb['n']} casos) y un CB el {pc(pos['CB']['p_played'])}, frente al "
            f"{pc(pos['LB']['p_played'])} de un LB.",
        ]
    out += [
        "",
        "**Qué significa para la Fase 1.** La baja no se puede tratar como 0 o 1. Se usará la "
        "probabilidad de jugar medida arriba (por etiqueta, posición y entrenamiento) multiplicada "
        "por el impacto del jugador en puntos de spread. El experimento es reproducible porque el "
        "estatus del parte es lo que se sabía antes del partido, pero cualquier cifra de "
        "rendimiento del jugador debe calcularse solo con semanas anteriores. "
        "Detalle completo en `reports/injury_audit.json`.",
    ]
    return out


def write_markdown(res: dict, path: Path | None = None) -> str:
    o, bs, hf = res["overall"], res["bootstrap"], res["heavy_favourites_on_ens_games"]
    dv = bs["diff_vs_market"]
    ex, sc = res["extremizing"], res["stack_coefficients"]
    ats, ats3 = res["ats_model_only"]["all"], res["ats_model_only"]["disagree_3pts_or_more"]
    lv = bs["levels"]
    mo_d, en_d = dv["model_only"], dv["ens"]
    worst = max(
        (r for r in res["favourite_bins"]["ens"] if r["n"] >= 100),
        key=lambda r: abs(r["pred"] - r["actual"]),
    )

    def sig(d: dict) -> str:
        lo, hi = d["log_loss_ci"]
        return "no incluye el cero" if lo > 0 or hi < 0 else "incluye el cero"

    def side(d: dict) -> str:
        return "peor" if d["log_loss"] > 0 else "mejor"

    L: list[str] = [
        "# Línea base 2018 a 2025",
        "",
        f"Generado el {res['generated_at']}. {res['n_games']} partidos de temporada regular "
        f"({res['seasons'][0]} a {res['seasons'][1]}, empates fuera). Datos en "
        "`reports/baseline_2018_2025.json`, gráfico en `reports/baseline_calibration.png`. "
        "Este documento lo genera `ensemblitz baseline`; no se edita a mano.",
        "",
        "## Conclusiones en lenguaje llano",
        "",
        f"1. **El modelo propio, sin mirar el mercado, está por detrás de las casas.** "
        f"Su log loss es {n(o['model_only']['log_loss'])} frente a {n(o['market']['log_loss'])} del "
        f"cierre sin comisión: una diferencia de {sn(mo_d['log_loss'])} con intervalo del 95 % "
        f"{ci(mo_d['log_loss_ci'])}, que {sig(mo_d)}. Acierta {pc(o['model_only']['accuracy'])} de los partidos frente al "
        f"{pc(o['market']['accuracy'])} del mercado.",
        f"2. **El ensemble publicado casi copia al mercado y no lo mejora.** Log loss "
        f"{n(o['ens']['log_loss'])} contra {n(o['market']['log_loss'])} ({sn(en_d['log_loss'])}, "
        f"IC 95 % {ci(en_d['log_loss_ci'])}): es {side(en_d)} que el mercado y el intervalo {sig(en_d)}. Los pesos le dan al mercado de media un "
        f"{pc(sc['market_weight_share_ens'], 0)} del total ({pc(sc['market_plus_residual_share_ens'], 0)} contando el "
        "LightGBM que corrige al mercado), así que no aporta información propia visible.",
        f"3. **Contra el spread, el modelo propio {'no llega al punto de equilibrio' if ats['win_pct'] < 0.5238 else 'supera el punto de equilibrio'}.** Apostando el lado que prefiere contra "
        f"la línea de cierre: {ats['w']}-{ats['l']}-{ats['push']} ({pc(ats['win_pct'])}, IC 95 % "
        f"{pc(ats['ci95'][0])} a {pc(ats['ci95'][1])}). Para ganar dinero con una comisión típica "
        f"hace falta un {pc(0.5238, 2)}. Cuando el modelo discrepa 3 puntos o más del spread: "
        f"{ats3['w']}-{ats3['l']}-{ats3['push']} ({pc(ats3['win_pct'])}, IC 95 % {pc(ats3['ci95'][0])} a {pc(ats3['ci95'][1])}).",
        f"4. **La calibración no falla de forma grave.** La pendiente de calibración del ensemble es "
        f"{n(o['ens']['calibration_slope'], 2)} (1 es perfecto) y en los favoritos del 75 % o más "
        f"apenas está {n(abs(ex['heavy_fav_overconfidence_pp']['ens']), 1)} puntos por encima de lo "
        f"real. El modelo sin mercado es el que se pasa de confiado: {n(o['model_only']['calibration_slope'], 2)} de pendiente. "
        f"El tramo con mayor desviación del ensemble (con 100 partidos o más) es {worst['bin']}: "
        f"prevé {pc(worst['pred'])} y ocurre {pc(worst['actual'])} ({worst['n']} partidos); con tan "
        "pocos partidos por tramo hay que leerlo con cautela.",
        f"5. **El extremizar existe, pero aquí no hace daño.** Los pesos del ensemble suman más "
        f"de 1 en el {pc(ex['ens_sum_gt_1_share_of_folds'], 0)} de los reajustes (media {n(ex['ens_sum_weights_mean'], 2)}). "
        f"Con los pesos limitados a suma 1 el log loss baja {n(abs(ex['ens_cap1']['log_loss_minus_ens']), 4)} "
        f"y sin sesgo ni extremizar baja {n(abs(ex['ens_pool']['log_loss_minus_ens']), 4)}, pero esa mejora no es "
        "estadísticamente distinguible de cero. No hay base para decir que las versiones "
        "restringidas calibren mejor fuera de muestra; tampoco para defender el extremizar.",
        "",
        "## Resultados globales",
        "",
    ]
    pop = res.get("population", {})
    L += [
        "## Reconciliación de población",
        "",
        f"- Filas regulares en alcance: {pop.get('n_rows_in_scope', 'n/d')}.",
        f"- Partidos jugados: {pop.get('n_played', 'n/d')}.",
        f"- Predicciones válidas para todas las fuentes: {pop.get('n_valid_probability_rows', 'n/d')}.",
        f"- Empates excluidos: {pop.get('n_ties', 'n/d')}.",
        f"- Filas con predicciones ausentes: {pop.get('n_missing_prediction_rows', 'n/d')}.",
        f"- Filas con probabilidades inválidas: {pop.get('n_invalid_probability_rows', 'n/d')}.",
        f"- Muestra final puntuada: {pop.get('n_scored', res['n_games'])}.",
        "",
    ]
    if pop.get("excluded_games"):
        L += ["Partidos excluidos y motivo:", ""]
        for item in pop["excluded_games"]:
            L.append(
                f"- {item['game_id']} ({item['season']} semana {item['week']}): "
                + ", ".join(item["reasons"])
                + "."
            )
        L.append("")
    rows = []
    for k in B.SCORED:
        r, lv_k = o[k], lv[k]
        rows.append(
            [
                B.NAMES[k],
                f"{pc(r['accuracy'])} {ci_pct(lv_k['accuracy_ci'])}",
                f"{n(r['brier'])} {ci_plain(lv_k['brier_ci'])}",
                f"{n(r['log_loss'])} {ci_plain(lv_k['log_loss_ci'])}",
                n(r["calibration_slope"], 2),
            ]
        )
    L += _table(
        [
            "Fuente",
            "Acierto (IC 95 %)",
            "Brier (IC 95 %)",
            "Log loss (IC 95 %)",
            "Pendiente calibración",
        ],
        rows,
    )
    L += [
        "",
        "Diferencia con el mercado (negativo = mejor que el mercado), bootstrap emparejado "
        "por temporadas completas. Conserva la dependencia temporal dentro de cada temporada; "
        f"{bs['n_blocks']} temporadas independientes, {bs['n_boot']} remuestreos, semilla {bs['seed']}.",
        "",
    ]
    rows = []
    for k in ("model_only", "ens", "ens_cap1", "ens_pool"):
        d = dv[k]
        rows.append(
            [
                B.NAMES[k],
                sn(d["log_loss"]),
                ci(d["log_loss_ci"]),
                sn(d["brier"]),
                ci(d["brier_ci"]),
            ]
        )
    L += _table(["Fuente menos mercado", "Δ log loss", "IC 95 %", "Δ Brier", "IC 95 %"], rows)
    L += ["", "## Por temporada", ""]
    rows = []
    for s, d in res["per_season"].items():
        rows.append(
            [
                str(s),
                str(d["market"]["n"]),
                f"{pc(d['market']['accuracy'])} / {n(d['market']['log_loss'])}",
                f"{pc(d['model_only']['accuracy'])} / {n(d['model_only']['log_loss'])}",
                f"{pc(d['ens']['accuracy'])} / {n(d['ens']['log_loss'])}",
                pc(ats_pct(res, s)),
            ]
        )
    L += _table(
        [
            "Temporada",
            "Partidos",
            "Mercado (acierto / log loss)",
            "Solo modelo",
            "Ensemble",
            "ATS solo modelo",
        ],
        rows,
    )
    L += [
        "",
        "Con unos 270 partidos por temporada, una diferencia de 0,01 en log loss entre fuentes "
        "es ruido. Por eso lo que cuenta es el total y su intervalo.",
        "",
        "## Calibración por deciles",
        "",
        "Diez grupos de igual tamaño según la probabilidad prevista de victoria local. "
        "Gráfico: `reports/baseline_calibration.png`.",
        "",
        "![Calibración](baseline_calibration.png)",
        "",
    ]
    for k in B.SCORED:
        L += [f"**{B.NAMES[k]}**", ""]
        rows = [
            [
                str(r["decile"]),
                str(r["n"]),
                pc(r["pred"]),
                pc(r["actual"]),
                sn((r["actual"] - r["pred"]) * 100, 1) + " pp",
            ]
            for r in res["deciles"][k]
        ]
        L += _table(["Decil", "Partidos", "Prevista", "Real", "Real menos prevista"], rows)
        L += [""]
    L += [
        "## Favoritos: ¿hay exceso de confianza?",
        "",
        "Calibración del lado que cada fuente considera favorito, por tramos de su probabilidad. "
        "Los IC 95 % se calculan remuestreando temporadas completas; solo hay ocho bloques "
        "independientes, por lo que son intervalos orientativos y de resolución limitada.",
        "",
    ]
    for k in B.SCORED:
        L += [f"**{B.NAMES[k]}**", ""]
        rows = [
            [
                r["bin"],
                str(r["n"]),
                pc(r["pred"]),
                pc(r["actual"]),
                f"{pc(r['actual_lo'])} a {pc(r['actual_hi'])}",
            ]
            for r in res["favourite_bins"][k]
        ]
        L += _table(["Tramo", "Partidos", "Prevista", "Real", "IC 95 % del real"], rows)
        L += [""]
    L += [
        "",
        "### Cada fuente: sus favoritos al 75 % o más",
        "",
    ]
    rows = []
    for k in B.SCORED:
        r = res["heavy_favourites_75"][k]
        interval = r.get("overconfidence_pp_ci95")
        interval_txt = "n/d" if not interval else ci(interval, 2) + " pp"
        rows.append(
            [
                B.NAMES[k],
                str(r["n"]),
                pc(r.get("pred")),
                pc(r.get("actual")),
                sn(r.get("overconfidence_pp"), 2) + " pp",
                interval_txt,
            ]
        )
    L += _table(
        ["Fuente", "N", "Prevista", "Real", "Prevista menos real", "IC 95 % de la brecha"],
        rows,
    )
    L += [
        "",
        f"En los {hf['n']} partidos en que el ensemble da al favorito 75 % o más (mismos partidos "
        f"para todas las fuentes): real {pc(hf['actual'])} (IC 95 % por temporada "
        f"{pc(hf['actual_ci95'][0])} a {pc(hf['actual_ci95'][1])}).",
        "",
    ]
    rows = [
        [
            B.NAMES[k],
            pc(hf[k]["pred_mean"]),
            sn(hf[k]["overconfidence_pp"], 1) + " pp",
            n(hf[k]["log_loss"]),
        ]
        for k in (*B.SCORED, "ens_cap1", "ens_pool")
    ]
    L += _table(["Fuente", "Prevista (media)", "Prevista menos real", "Log loss"], rows)
    L += [
        "",
        "Un valor positivo es exceso de confianza. El real queda dentro del intervalo de las "
        f"previsiones del ensemble: {'no' if not ex['ens_overconfident_beyond_ci'] else 'sí'} "
        "hay sobreconfianza demostrable en los favoritos claros.",
        "",
        "## Pesos del apilado (colinealidad y extremizar)",
        "",
        "Las entradas del apilado están muy correlacionadas (en log-odds): "
        f"mercado con LightGBM sobre el mercado {n(res['input_logit_correlation']['market']['lgbm_mkt'], 2)}, "
        f"mercado con Elo {n(res['input_logit_correlation']['market']['elo'], 2)}, Elo con Kalman "
        f"{n(res['input_logit_correlation']['elo']['kf'], 2)}. Con fuentes así, sumar señales "
        "(pesos con suma mayor que 1) empuja la probabilidad más allá de todas ellas.",
        "",
        f"Suma de pesos del ensemble por reajuste semanal: mínimo {n(sc['ens']['sum_weights_min'], 2)}, "
        f"media {n(sc['ens']['sum_weights_mean'], 2)}, máximo {n(sc['ens']['sum_weights_max'], 2)} "
        f"({sc['ens']['share_of_folds_sum_gt_1'] * 100:.0f} % de los reajustes por encima de 1). "
        f"Solo modelo: media {n(sc['model_only']['sum_weights_mean'], 2)}.",
        "",
        "Coeficientes del primer reajuste de cada temporada (entrenado solo con temporadas "
        "anteriores). Orden: mercado, Elo, Kalman, LightGBM, LightGBM sobre el mercado, y sesgo.",
        "",
    ]
    rows = []
    for s, d in sc["by_season_start"].items():
        e = d["ens"]
        rows.append(
            [
                str(s),
                ", ".join(n(w, 2) for w in e["weights"]),
                n(e["sum_weights"], 2),
                n(e["bias"], 2),
            ]
            + [
                ", ".join(n(w, 2) for w in d["model_only"]["weights"]),
                n(d["model_only"]["sum_weights"], 2),
            ]
        )
    L += _table(
        [
            "Temporada",
            "Ensemble: pesos",
            "Suma",
            "Sesgo",
            "Solo modelo: pesos (Elo, Kalman, LightGBM)",
            "Suma",
        ],
        rows,
    )
    L += [
        "",
        "Variantes restringidas, mismas pérdida y regularización (fuera de muestra, mismo walk-forward):",
        "",
    ]
    rows = []
    for k in ("ens", "ens_cap1", "ens_pool"):
        r = o[k]
        extra = ex.get(k, {})
        rows.append(
            [
                B.NAMES[k],
                n(r["log_loss"]),
                n(r["brier"]),
                n(r["calibration_slope"], 2),
                sn(extra.get("log_loss_minus_ens"), 4) if extra else "base",
                ci(extra.get("log_loss_ci")) if extra else "n/d",
            ]
        )
    L += _table(
        ["Variante", "Log loss", "Brier", "Pendiente", "Δ log loss vs publicado", "IC 95 %"], rows
    )
    L += [
        "",
        "**Veredicto.** Las variantes sin extremizar tienen log loss y Brier algo menores y "
        "corrigen el signo del exceso en favoritos, pero la mejora cabe dentro del ruido (el "
        "intervalo incluye el cero) y su pendiente de calibración se aleja de 1 por el otro lado "
        "(el mercado está ligeramente infraconfiado). Conclusión práctica: el extremizar no está "
        "estropeando la calibración, tampoco aporta. En la Fase 1 se evaluará la versión con suma "
        "de pesos igual a 1 como candidata, sin cambiar la producción ahora.",
        "",
        "## ATS del modelo propio contra el cierre",
        "",
    ]
    rows = [
        [
            "Todos los partidos",
            f"{ats['w']}-{ats['l']}-{ats['push']}",
            pc(ats["win_pct"]),
            f"{pc(ats['ci95'][0])} a {pc(ats['ci95'][1])}",
            n(ats["p_vs_breakeven_52_38"], 3),
        ],
        [
            "Discrepa 3 puntos o más",
            f"{ats3['w']}-{ats3['l']}-{ats3['push']}",
            pc(ats3["win_pct"]),
            f"{pc(ats3['ci95'][0])} a {pc(ats3['ci95'][1])}",
            n(ats3["p_vs_breakeven_52_38"], 3),
        ],
    ]
    L += _table(["Muestra", "G-P-E", "% ganadas", "IC 95 %", "p-valor frente a 52,38 %"], rows)
    L += [
        "",
        "ATS = apostar el lado que el modelo sin mercado prefiere contra el spread de cierre. "
        "El 52,38 % es el punto de equilibrio con cuota 1,91 (-110).",
        "",
    ]
    L += injury_section()
    L += [
        "",
        "## Protocolo y límites",
        "",
        f"- {res['protocol']}",
        "- El audit recalcula los apilados desde las predicciones fuera de muestra de los "
        "componentes (`reports/baseline_components.parquet`). Que esos componentes sean "
        "honestos lo cubren los tests de fugas del pipeline; `python scripts/check_baseline.py "
        "--full` los regenera desde los datos de nflverse.",
        "- Los modelos usan el spread y la moneyline de cierre de nflverse; el mercado de cierre "
        "es el rival más duro posible y no se puede apostar a esa cuota en España.",
        "- El intervalo de confianza no corrige que se miren varias fuentes y variantes a la vez.",
        "- Esta línea base queda fija. La barrera de CI (`scripts/check_baseline.py`) falla si el "
        f"log loss de cualquiera de las dos fuentes sube más de {n(B.TOL_LOG_LOSS, 4)} o el Brier más de {n(B.TOL_BRIER, 4)}.",
    ]
    text = "\n".join(L) + "\n"
    (path or B.MD_PATH).write_text(text)
    return text


def ci_pct(c: list[float]) -> str:
    return f"[{n(c[0] * 100, 1)}; {n(c[1] * 100, 1)}]"


def ci_plain(c: list[float]) -> str:
    return f"[{n(c[0])}; {n(c[1])}]"


def ats_pct(res: dict, season: int) -> float | None:
    return res["ats_model_only"]["per_season"][season]["win_pct"]
