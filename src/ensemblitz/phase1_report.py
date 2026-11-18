"""Spanish markdown for the Phase 1 audit (every number comes from the audit dict)."""

from __future__ import annotations

import json
from pathlib import Path

from ensemblitz import config as C
from ensemblitz import phase1 as P
from ensemblitz.baseline_report import _table, ci, n, pc, sn

AVAIL_PATH = C.REPORTS_DIR / "phase1_availability.json"
GROUP_ES = {
    "QB": "QB",
    "SKILL": "RB, WR y TE",
    "OL": "Línea ofensiva",
    "FRONT": "Frente defensivo (EDGE, DT, LB)",
    "SECONDARY": "Secundaria (CB, S)",
}


def write_markdown(res: dict, path: Path | None = None) -> str:
    o, pb, v = res["overall"], res["paired_bootstrap"], res["verdict"]
    inj = pb["D_inj__minus__C_discrete"]
    tot = pb["D_total__minus__C_discrete"]
    me = res["margin_error"]["injuries_vs_without"]
    ols, olm = res["ols_full_sample"], res["ols_vs_market_spread"]
    adj = res["adjustment"]
    a0, a1 = res["ats"]["without_injuries"]["all"], res["ats"]["with_injuries"]["all"]
    mk = pb["D_inj__minus__market"]
    mt35 = res["margin_table"]
    if v["significant_at_95"]:
        head = (
            "**Veredicto: las lesiones mejoran el log loss fuera de muestra de forma "
            "significativa.** Se puede conectar a producción."
        )
    else:
        head = (
            "**Veredicto: las lesiones mejoran un poco la estimación, pero no de forma "
            "significativa con el 95 %. No se conecta a producción.** El intervalo del "
            f"log loss es {ci(v['log_loss_ci'])} y llega a tocar el cero."
        )
    L = [
        "# Fase 1: impacto de lesiones por jugador",
        "",
        f"Generado el {res['generated_at']}. {res['n_games']} partidos de temporada regular "
        f"({res['seasons'][0]} a {res['seasons'][1]}), walk-forward estricto: valor del jugador, "
        "probabilidad de jugar, coeficientes de cada grupo, tabla de márgenes y desviación típica "
        "se calculan antes de cada semana solo con semanas anteriores. Datos en "
        "`reports/phase1_injuries.json`; lo genera `ensemblitz phase1`, no se edita a mano.",
        "",
        head,
        "",
        "## Conclusiones en lenguaje llano",
        "",
        f"1. **Efecto de las lesiones (comparación principal, fijada antes de mirar).** "
        f"Mismo margen del modelo sin mercado y misma conversión a probabilidad, con y sin el "
        f"ajuste por lesiones: log loss {sn(inj['ll']['diff'])} (IC 95 % {ci(inj['ll']['ci'])}), "
        f"Brier {sn(inj['br']['diff'])} ({ci(inj['br']['ci'])}). El error del margen baja "
        f"{n(abs(me['diff']), 2)} puntos² (IC {ci(me['ci'], 2)}). "
        + (
            "El Brier sí queda por debajo de cero por muy poco, el log loss no: es un resultado "
            "de frontera, no una prueba."
            if inj["br"]["ci"][1] < 0 <= inj["ll"]["ci"][1]
            else ""
        ),
        f"2. **Hay señal real, pero pequeña.** El ajuste medio es de {n(adj['mean_abs_points'], 1)} "
        f"puntos de spread por partido y solo {adj['games_abs_ge_2']} partidos pasan de 2 puntos. "
        f"Un punto de spread vale unos 3 puntos de probabilidad de victoria, así que casi nunca "
        f"cambia el ganador previsto. Con un solo coeficiente para todas las lesiones "
        f"(exploratorio) el efecto es {sn(tot['ll']['diff'])} ({ci(tot['ll']['ci'])}); "
        f"el coeficiente total vale {n(ols['total']['beta'], 2)} ± {n(ols['total']['se'], 2)} "
        "en el ajuste de toda la muestra. Esa variante se probó después de ver el resultado "
        "principal, así que no se usa para decidir.",
        f"3. **Seguimos lejos del mercado.** El candidato con lesiones tiene {sn(mk['ll']['diff'])} "
        f"de log loss frente al cierre (IC {ci(mk['ll']['ci'])}). Las lesiones cierran una parte "
        "pequeña de la distancia, no la mayoría.",
        f"4. **Contra el spread no cambia nada.** ATS del margen sin lesiones: "
        f"{a0['w']}-{a0['l']}-{a0['push']} ({pc(a0['win_pct'])}); con lesiones: "
        f"{a1['w']}-{a1['l']}-{a1['push']} ({pc(a1['win_pct'])}). Ambos por debajo del 52,38 % de "
        "equilibrio.",
        f"5. **El mercado ya descuenta las lesiones.** Al explicar lo que el spread de cierre se "
        f"deja ({'resultado menos spread'}) con las mismas cargas de lesiones, el coeficiente total "
        f"es {n(olm['total']['total']['beta'], 2)} ± {n(olm['total']['total']['se'], 2)}: "
        f"{'indistinguible de cero' if abs(olm['total']['total']['beta']) < 2 * olm['total']['total']['se'] else 'distinto de cero'}. "
        "Las lesiones ayudan a un modelo que no mira el mercado porque el mercado ya las usa.",
        f"6. **La tabla discreta de márgenes no mejora la probabilidad de victoria.** Frente a la "
        f"curva normal el log loss cambia {sn(pb['C_discrete__minus__B_normal']['ll']['diff'])} "
        f"({ci(pb['C_discrete__minus__B_normal']['ll']['ci'])}). Los números clave importan para "
        "la probabilidad de cubrir un spread, no para quién gana. Y la tabla todavía no cubre bien "
        f"ese caso: con línea de 3,5 da {pc(mt35['p_cover_at_own_line_discrete'][2])} de cubrir y los "
        f"favoritos reales cubrieron {pc(mt35['observed_favourite_cover'][2]['cover'])}. No debe usarse "
        "para cubrir o valor esperado hasta corregirla (fase posterior).",
        "",
        "## Resultados (mismos partidos para todas las filas)",
        "",
    ]
    rows = []
    for k, lab in P.VARIANTS.items():
        r = o[k]
        rows.append(
            [
                lab,
                pc(r["accuracy"]),
                n(r["brier"], 4),
                n(r["log_loss"], 4),
                n(r["calibration_slope"], 2),
            ]
        )
    L += _table(["Variante", "Acierto", "Brier", "Log loss", "Pendiente calibración"], rows)
    L += [
        "",
        "Diferencias por pares (bootstrap por partidos, "
        f"{P.BOOT} remuestreos, negativo = el primero es mejor):",
        "",
    ]
    names = {
        "D_inj__minus__C_discrete": "Con lesiones menos sin lesiones (principal)",
        "C_discrete__minus__B_normal": "Tabla discreta menos curva normal (sin lesiones)",
        "D_inj__minus__A_stack": "Candidato menos pila lógica de la fase 0",
        "C_discrete__minus__A_stack": "Sin lesiones, tabla discreta menos pila de la fase 0",
        "D_inj__minus__market": "Candidato menos mercado",
        "C_discrete__minus__market": "Sin lesiones menos mercado",
        "A_stack__minus__market": "Pila de la fase 0 menos mercado",
        "D_total__minus__C_discrete": "Un solo coeficiente menos sin lesiones (exploratorio)",
        "D_binary__minus__C_discrete": "Lesiones sí/no menos sin lesiones (exploratorio)",
        "D_binary__minus__D_inj": "Sí/no menos probabilidades de jugar (exploratorio)",
    }
    rows = []
    for k, lab in names.items():
        d = pb[k]
        rows.append(
            [
                lab,
                sn(d["ll"]["diff"]),
                ci(d["ll"]["ci"]),
                sn(d["br"]["diff"]),
                ci(d["br"]["ci"]),
                sn(d["ac"]["diff"] * 100, 1) + " pp",
            ]
        )
    L += _table(["Comparación", "Δ log loss", "IC 95 %", "Δ Brier", "IC 95 %", "Δ acierto"], rows)
    sb = res.get("subset_big_adjustment") or {}
    if sb:
        d = sb["paired"]["D_inj__minus__C_discrete"]
        L += [
            "",
            f"En los {sb['n']} partidos con un ajuste de 1 punto o más (donde hay más efecto): "
            f"Δ log loss {sn(d['ll']['diff'])} (IC {ci(d['ll']['ci'])}), error del margen "
            f"{sn(sb['mse']['diff'], 2)} puntos² (IC {ci(sb['mse']['ci'], 2)}).",
        ]
    ex = res.get("exploratory_2020_2025")
    if ex:
        d = ex["paired"]["D_inj__minus__C_discrete"]
        L += [
            "",
            f"Solo 2020 a 2025 ({ex['n']} partidos, periodo elegido después de ver la tabla por "
            f"temporada, orientativo): Δ log loss {sn(d['ll']['diff'])} (IC {ci(d['ll']['ci'])}). "
            "En 2018 y 2019 los coeficientes aún venían casi del prior y empeoran el resultado.",
        ]
    L += ["", "## Por temporada (log loss)", ""]
    rows = []
    for s, d in res["per_season"].items():
        rows.append(
            [
                str(s),
                str(d["market"]["n"]),
                n(d["market"]["log_loss"], 3),
                n(d["C_discrete"]["log_loss"], 3),
                n(d["D_inj"]["log_loss"], 3),
                sn(d["D_inj"]["log_loss"] - d["C_discrete"]["log_loss"], 4),
            ]
        )
    L += _table(["Temporada", "Partidos", "Mercado", "Sin lesiones", "Con lesiones", "Δ"], rows)
    L += ["", "## Qué pesa cada grupo", ""]
    L += [
        "Coeficiente = cuántos puntos de margen se pierden por cada punto de impacto esperado "
        "(1 significaría que el valor por jugador está bien escalado). Ajuste de toda la muestra "
        "por mínimos cuadrados, error típico clásico:",
        "",
    ]
    rows = []
    for g in P.GROUPS:
        r = ols[g]
        rows.append(
            [
                GROUP_ES[g],
                n(r["beta"], 2),
                n(r["se"], 2),
                ci(r["ci95"], 2),
                n(olm["grupos"][g]["beta"], 2) + " ± " + n(olm["grupos"][g]["se"], 2),
            ]
        )
    L += _table(
        ["Grupo", "Coeficiente", "Error típico", "IC 95 %", "Frente al spread del mercado"], rows
    )
    L += [
        "",
        "Los grupos con más datos y señal son QB y RB/WR/TE. Línea ofensiva, frente defensivo y "
        "secundaria tienen intervalos que incluyen el cero y el uno: con este diseño no se pueden "
        "separar. El QB ya entra en el modelo base por su identidad (el titular anunciado), así "
        "que su coeficiente mide sobre todo la duda del QB `Questionable`.",
        "",
        "Coeficientes walk-forward al empezar cada temporada (los que se usan de verdad, con "
        f"ridge hacia {n(P.PRIOR_BETA, 1)}):",
        "",
    ]
    rows = [
        [str(s)] + [n(b[g], 2) for g in P.GROUPS] for s, b in res["betas_by_season_start"].items()
    ]
    L += _table(["Temporada", *P.GROUPS], rows)
    L += ["", "## Probabilidad de jugar según el parte", ""]
    if AVAIL_PATH.exists():
        av = json.loads(AVAIL_PATH.read_text())
        L += [
            f"Estimada con partes y snaps anteriores a {av['estimated_before']}, con "
            "reducción jerárquica (etiqueta, entrenamiento, posición). Solo cuentan jugadores "
            "con etiqueta o con entrenamiento limitado o sin entrenar:",
            "",
        ]
        rows = []
        for k, c in av["cells"].items():
            lab, pr = k.split("|")
            rows.append(
                [
                    lab,
                    {"full": "completo", "limited": "limitado", "dnp": "no entrenó"}[pr],
                    str(c["n"]),
                    pc(c["p_play"], 0),
                    pc(c["p_play_qb"], 0),
                    pc(c["p_play_cb"], 0),
                    pc(c["p_play_ol"], 0),
                ]
            )
        L += _table(["Etiqueta", "Entrenamiento", "Casos", "WR", "QB", "CB", "OL"], rows)
    mt = res["margin_table"]
    L += [
        "",
        "## Tabla discreta de márgenes de la NFL",
        "",
        "Se estima con todos los partidos anteriores desde 1999 (spread de cierre como margen "
        f"esperado), con desviación típica {n(mt['sigma'], 1)}. Peso de cada margen absoluto frente a "
        "una curva normal (1 = igual):",
        "",
    ]
    rows = [[k, n(w, 2)] for k, w in mt["tilt_w"].items()]
    L += _table(["Margen absoluto", "Peso"], rows)
    L += [
        "",
        "Probabilidad de que el favorito local gane, y de que cubra la línea, según la tabla "
        "discreta y la curva normal, junto a la frecuencia real con la que cubrieron los "
        "favoritos con esa línea (todos los partidos desde 1999):",
        "",
    ]
    rows = []
    for i, ln in enumerate(mt["expected_margin_lines"]):
        rows.append(
            [
                n(ln, 1),
                pc(mt["p_win_discrete"][i]),
                pc(mt["p_win_normal"][i]),
                pc(mt["p_cover_at_own_line_discrete"][i]),
                pc(mt["p_cover_at_own_line_normal"][i]),
                f"{pc(mt['observed_favourite_cover'][i]['cover'])} ({mt['observed_favourite_cover'][i]['n']})",
            ]
        )
    L += _table(
        [
            "Spread local",
            "Gana (tabla)",
            "Gana (normal)",
            "Cubre (tabla)",
            "Cubre (normal)",
            "Cubre, histórico (partidos)",
        ],
        rows,
    )
    L += [
        "",
        "## Límites y qué sigue",
        "",
        "- El parte de lesiones es el último de la semana (jueves a sábado), no una foto de 24 "
        "horas antes. La predicción de los martes no puede usarlo: hay que actualizar el viernes.",
        "- El valor por jugador usa EPA, snaps y producción pública. La línea ofensiva y la "
        "defensa no tienen estadística individual y entran por prior y cuota de snaps; es lo más "
        "débil del modelo.",
        "- El QB titular ya está en el modelo base (nflverse anuncia el titular). Con un QB `Out` "
        "se cuenta dos veces solo en parte; el coeficiente walk-forward lo absorbe.",
        "- Se probaron tres variantes de lesiones y dos conversiones; solo la principal está "
        "fijada de antemano. El resto es exploratorio.",
        "- No se ha cambiado producción: `ensemblitz predict`, la web y el baseline de CI siguen "
        "igual.",
    ]
    text = "\n".join(L) + "\n"
    (path or P.MD_PATH).write_text(text)
    return text
