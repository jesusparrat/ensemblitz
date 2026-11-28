"""Every user-facing string of the site, in Spanish (default) and English.

Both tables must have exactly the same keys (tests/test_site.py checks it, and that every key
used by a template exists). ``{name}`` marks a placeholder. Spanish uses comma decimals, a narrow
no-break space before ``%`` and no em dashes (the project's anti-slop rules); English uses dots.
Team names are the official English ones in both languages.
"""

from __future__ import annotations

PC = "\u202f%"  # narrow no-break space and percent sign, Spanish style

ES: dict[str, str] = {
    "na": "n/d",
    "even": "igualado",
    "tie": "empate",
    "night_thu": "jueves noche en EE.\u202fUU.",
    "night_mon": "lunes noche en EE.\u202fUU.",
    "night_sun": "domingo noche en EE.\u202fUU.",
    "status_out": "Baja",
    "status_doubtful": "Muy dudoso",
    "status_questionable": "Dudoso",
    "status_returning": "Vuelve",
    "status_other": "Novedad",
    "site.title": "Pronósticos NFL",
    "site.description": (
        "Quién gana cada partido de la NFL, por cuánto y cuántos puntos se esperan, con la "
        "predicción de un modelo propio contrastada con el mercado. Picks guardados antes del saque."
    ),
    # navigation and chrome
    "nav.skip": "Saltar al contenido",
    "nav.home_aria": "ensemblitz, inicio",
    "nav.aria": "Secciones",
    "nav.week": "Jornada",
    "nav.history": "Historial",
    "nav.method": "Método",
    "nav.verify": "Verificar",
    "nav.code": "Código",
    "nav.data_of": "Datos del {when}",
    "nav.lang_aria": "Read this page in English",
    "nav.theme_aria": "Cambiar entre tema claro y oscuro",
    "foot.generated": "Últimos picks guardados el {when}. Se guardan antes del saque y no se editan.",
    "foot.license": "Licencia MIT. Datos de nflverse bajo licencia CC-BY 4.0. Tipografías Archivo e IBM Plex Mono con licencia SIL OFL.",
    # week page
    "week.title": "Jornada {week}",
    "week.h1": "Jornada {week}",
    "week.lede": (
        "Temporada NFL {season}: probabilidades, puntos esperados y márgenes de un modelo "
        "estadístico propio que no usa las cuotas, guardados antes del saque. Comparamos cada "
        "lectura con el mercado como referencia; horas de Madrid."
    ),
    "week.read_aria": "Resumen de la jornada",
    "week.read_games": "partidos en la jornada",
    "week.read_flags": "partidos donde diferimos del mercado",
    "week.read_next": "{away} en {home}",
    "week.read_next_live": "hasta {away} en {home}",
    "week.read_hits": "picks acertados",
    "week.nav": "Jornadas",
    "week.nav_aria": "Jornadas",
    "week.nav_item": "Jornada {w}",
    "week.legend": (
        "Puntos esperados por equipo y, entre paréntesis, el rango que cubre el 80\u202f% de los "
        "resultados simulados."
    ),
    "week.legend_flag": "Filete amarillo: nuestra probabilidad se separa {n} puntos o más de la del mercado (desacuerdo entre lecturas, no ventaja).",
    "week.legacy": (
        "Algunos partidos de esta jornada se guardaron antes del cambio de modelo y muestran el "
        "pick de entonces, que mezclaba modelo y mercado. Se indica en cada uno."
    ),
    "filter.label": "Filtrar partidos",
    "filter.all": "Todos",
    "filter.flags": "Donde diferimos del mercado",
    "filter.team": "Mi equipo",
    "filter.empty": "Ningún partido coincide con los filtros activos.",
    "team.label": "Seguir equipo",
    "team.none": "Ninguno",
    "cols.time": "Hora",
    "cols.game": "Partido",
    "cols.win": "Gana",
    "cols.points": "Puntos esperados",
    "cols.margin": "Margen",
    "cols.total": "Total",
    "day.games_one": "{n} partido",
    "day.games_n": "{n} partidos",
    "day.night": "{night}",
    "notes.aria": "Notas",
    "notes.saved": "Picks guardados el {when}.",
    "notes.market_books": "«Mercado» es el consenso agregado de The Odds API (sin margen).",
    "notes.market_nflverse": "«Mercado» es la línea pre-partido de nflverse (sin margen).",
    "notes.method": "Cómo lo medimos.",
    "notes.disclaimer": "Es un ejercicio de estadística, no una recomendación de apuesta.",
    # card
    "card.at": "en",
    "card.wins": "Gana {team}",
    "card.win_aria": "{team} gana con una probabilidad del {p}",
    "card.market": "Mercado: {p} (nosotros {d})",
    "card.market_flagged": "Mercado: {p}",
    "card.final": "Final: {away} {a}, {home} {h}.",
    "card.hit": "Pick acertado.",
    "card.miss": "Pick fallado.",
    "card.hit_short": "Acierto",
    "card.miss_short": "Fallo",
    "card.absences": "Bajas notables: {list}.",
    "card.absence_item": "{player} ({team}, {status}, {pts} pts)",
    "card.absences_note": "Contexto: no está incluido en el número.",
    "card.band_happened": "Esto pasó.",
    "card.band_outside": "El resultado quedó fuera de estos tres.",
    "band.away_15": "{team} por 15 o más",
    "band.away_8_14": "{team} por 8 a 14",
    "band.away_1_7": "{team} por 1 a 7",
    "band.tie": "Empate",
    "band.home_1_7": "{team} por 1 a 7",
    "band.home_8_14": "{team} por 8 a 14",
    "band.home_15": "{team} por 15 o más",
    "game.bands_h": "Márgenes más probables",
    "game.bands_note": "Los tres márgenes con más peso en la simulación del marcador. Un empate es su propia banda.",
    # news
    "news.title": "Última hora",
    "news.note": "Contexto: no se aplica a las cifras de la predicción.",
    "news.source": "fuente",
    # game page
    "game.description": "{away} en {home}: gana {fav} con un {p}. Puntos esperados, margen, total y contexto.",
    "game.week_ctx": "Jornada {week}, temporada {season}.",
    "game.tz_note": "(hora de Madrid)",
    "game.read_aria": "Resumen del partido",
    "game.margin_of": "margen, {txt}",
    "game.total_label": "puntos en total",
    "game.market_label": "probabilidad del mercado",
    "game.legacy": (
        "Este partido se guardó antes del cambio de modelo: su pick mezclaba modelo y mercado y "
        "no tiene rangos por equipo."
    ),
    "game.points_h": "Puntos esperados",
    "game.col_team": "Equipo",
    "game.col_exp": "Esperados",
    "game.col_range": "Rango del 80\u202f%",
    "game.row_margin": "Margen",
    "game.row_total": "Total",
    "game.margin_range": "{lo} a {hi}",
    "game.range_note": (
        "El rango deja fuera el 10\u202f% de los resultados simulados más bajos y el 10\u202f% de los más altos."
    ),
    "game.example": (
        "Un marcador de ejemplo: {away} {a}, {home} {h}. Es uno entre muchos posibles y ninguno "
        "llega al 2\u202f% de probabilidad."
    ),
    "game.market_h": "Frente al mercado",
    "game.ours": "Nuestro modelo",
    "game.market": "Mercado",
    "game.diff": "Diferencia",
    "game.market_src_label": "Fuente",
    "game.market_src_odds_api": "Consenso The Odds API ({n} operadores, sin margen)",
    "game.market_src_nflverse_pre": "Línea pre-partido de nflverse (sin margen)",
    "game.market_src_nflverse_close": "Línea histórica de nflverse (sin margen)",
    "game.market_time_fetched": "Descargado el {when} (caché de The Odds API).",
    "game.market_time_captured": "Capturado el {when} (instantánea de cuotas).",
    "game.market_time_read": "Leído el {when} (al generar la predicción).",
    "game.ref_line_h": "Línea de referencia (nflverse)",
    "game.line": "Spread y total",
    "game.line_total": "total {v}",
    "game.ref_line_note": "Datos del calendario pre-partido de nflverse; fuente distinta al consenso de probabilidad de The Odds API.",
    "game.market_src_books": "El mercado es el consenso de {n} operadores (The Odds API), sin su margen.",
    "game.market_src_nflverse": "El mercado es la línea pre-partido de nflverse, sin su margen.",
    "game.market_note": "Es solo una referencia: no usamos sus cifras para calcular las nuestras.",
    "game.flag_text": (
        "El modelo da a {fav} un {ours} y el mercado un {mkt}: {d} puntos de diferencia. En "
        "2018-2025, con brechas de {n} puntos o más (506 de 2133 partidos), el modelo acertó un "
        "59,9\u202f% (IC 95\u202f%: 56,1\u202f% a 63,7\u202f%) frente al 65,8\u202f% del mercado histórico "
        "(61,5\u202f% a 70,2\u202f%). Esta marca indica desacuerdo entre lecturas, no una ventaja."
    ),
    "game.close_text": "El modelo da a {fav} un {ours} y el mercado un {mkt}: lecturas parecidas.",
    "game.context_h": "Contexto",
    "game.absences_h": "Bajas notables",
    "game.absence": "{player} ({team}): {status}. Valor aproximado: {pts} puntos de margen por partido.",
    "game.absences_note": (
        "Es contexto y no entra en las cifras de arriba. Los puntos son una estimación del valor "
        "del jugador sobre su reemplazo. En las pruebas de 2018 a 2025, ajustar el número por "
        "lesiones no mejoró la predicción de forma significativa."
    ),
    "game.dist_h": "Cuánto puede variar",
    "game.chart_margin": "Margen simulado (local menos visitante)",
    "game.chart_total": "Total de puntos simulado",
    "game.dist_note": "Cada barra es la frecuencia de un resultado entre miles de partidos simulados.",
    "game.tech_h": "Detalle técnico",
    "game.tech_src": "Fuente",
    "game.tech_prob": "Probabilidad de {team}",
    "game.tech_note": "Los tres primeros modelos forman el número del titular. LightGBM sobre el mercado y la mezcla usan la referencia pre-partido de nflverse como entrada.",
    "game.back": "Volver a la jornada {week}",
    "game.copy_link": "Copiar enlace",
    "game.copied": "Enlace copiado",
    "game.copy_fail": "No se pudo copiar el enlace",
    "fact.rest": "Descanso",
    "fact.rest_v": "{home} {h} días, {away} {a} días",
    "fact.trip": "Viaje del visitante",
    "fact.trip_v": "{away}, {km} km",
    "fact.qb": "QB titular",
    "fact.qb_change": "cambio de titular en {teams}",
    "fact.qb_same": "sin cambios respecto al último partido",
    "fact.venue": "Estadio",
    "fact.venue_dome": "Cubierto o con techo cerrado",
    "fact.venue_open": "Aire libre, {temp}, viento {wind}",
    "fact.venue_open_nowx": "Aire libre. El tiempo previsto todavía no entra en el modelo",
    "chart.line": "nflverse {v}",
    "chart.wins": "gana {team}",
    "chart.points": "puntos totales",
    "chart.margin_aria": "Distribución del margen simulado (local menos visitante)",
    "chart.total_aria": "Distribución del total de puntos simulado",
    # the one-sentence reason
    "why_qb": "Lo que más pesa: {team} cambia de quarterback titular respecto a su último partido.",
    "why_rest": "Lo que más pesa: {team} llega con {n} días de descanso y su rival con {m}.",
    "why_trip": "Lo que más pesa: {team} viaja {km} km para visitar a {home}.",
    "why_wind": "Lo que más pesa: viento de {wind}, que resta juego aéreo.",
    "why_home": "Partido parejo: la ventaja de jugar en casa inclina el pick hacia {team}.",
    "why_away_close": "Partido parejo: {team} es algo mejor, incluso jugando fuera.",
    "why_form": "Lo que más pesa: la forma reciente. El modelo ve a {team} claramente por encima de {other}.",
    "why_v1": (
        "Duelo más marcado: ataque de {unit} de {off} (#{off_rank}) frente a defensa de {unit} "
        "de {dfn} (#{def_rank}). El mayor peso del margen en el modelo procede de {comp}."
    ),
    "why_v1_qb": (
        "Cambio de QB titular en {qb_teams}. Duelo más marcado: ataque de {unit} de {off} "
        "(#{off_rank}) frente a defensa de {unit} de {dfn} (#{def_rank}); mayor peso del margen "
        "en {comp}."
    ),
    "unit_pass": "pase",
    "unit_rush": "carrera",
    "comp_short_elo": "Elo",
    "comp_short_kf": "Kalman",
    "comp_short_lgbm": "LightGBM",
    "game.matchups_h": "Duelos a vigilar",
    "game.m_col_unit": "Duelo",
    "game.m_col_off": "Ataque (EPA/jug.)",
    "game.m_col_def": "Defensa permitida",
    "game.m_col_comp": "Comparativa",
    "game.m_row": "{unit}: {off} vs {dfn}",
    "game.m_rank_val": "#{rank} ({val})",
    "game.m_favors": "Inclina hacia {team} ({val})",
    "game.m_note": (
        "EPA por jugada ajustada por rival en ataque (más alto = mejor) y EPA permitida por "
        "jugada en defensa (más bajo = mejor), con rankings pre-partido 1 a 32 (empates por "
        "orden alfabético). La comparativa suma ataque más defensa permitida: es una lectura "
        "descriptiva, no un efecto causal ni una predicción de margen."
    ),
    "game.m_early_note": (
        "Inicio de temporada (jornada {week}): los ratings pre-partido combinan pocos partidos "
        "recientes con encogimiento fuerte hacia la media de la liga."
    ),
    "game.qb_h": "Quarterbacks (EPA por dropback)",
    "game.qb_row": "{team}",
    "game.qb_val": "{epa} EPA/dropback ({db} dropbacks efectivos)",
    "game.qb_diff_label": "Diferencia (local menos visitante)",
    "game.qb_note": (
        "Media ponderada con decaimiento temporal de EPA por dropback del titular previsto "
        "(datos pre-partido de nflverse, sin ajuste por rival)."
    ),
    "game.absences_cutoff": (
        "Diagnóstico de contexto de nflverse (corte {when}); no entra en ninguna probabilidad ni margen."
    ),
    "game.tech_stack_h": "Agregación exacta del titular (stack sin mercado)",
    "game.tech_stack_col_pw": "Peso logit",
    "game.tech_stack_col_lc": "Aporte logit",
    "game.tech_stack_col_mw": "Peso margen",
    "game.tech_stack_col_mc": "Aporte margen",
    "game.tech_stack_bias": "Sesgo logit (Platt)",
    "game.tech_stack_note": (
        "Probabilidad del titular = sigmoide(suma de aportes logit + sesgo). Margen del titular = "
        "suma de aportes de margen (local menos visitante)."
    ),
    "game.tech_lgbm_h": "Atribuciones TreeSHAP de LightGBM (solo componente LightGBM)",
    "game.tech_lgbm_col_grp": "Grupo de variables",
    "game.tech_lgbm_col_val": "Aporte al margen de LightGBM",
    "game.tech_lgbm_base": "Valor base de LightGBM",
    "game.tech_lgbm_pred": "Margen predicho por LightGBM",
    "game.tech_lgbm_note": (
        "Descomposición exacta TreeSHAP del componente LightGBM sin mercado (local menos visitante). "
        "No explica el stack completo ni redistribuye pesos de Kalman o Elo."
    ),
    "grp_pass_game": "Juego aéreo (EPA pase)",
    "grp_rush_game": "Juego terrestre (EPA carrera)",
    "grp_efficiency": "Tasa de éxito",
    "grp_qb": "Quarterback (EPA/dropback y cambios)",
    "grp_team_strength": "Fuerza global previa (Kalman y Elo)",
    "grp_situational": "Situacional (descanso, viaje, campo, clima)",
    "game.tech_kf_h": "Descomposición exacta de Kalman (solo componente Kalman)",
    "game.tech_kf_hfa": "Factor campo de Kalman",
    "game.tech_kf_h_vs_a": "Ataque {home} + defensa permitida {away}",
    "game.tech_kf_a_vs_h": "Menos (ataque {away} + defensa permitida {home})",
    "game.tech_kf_total": "Margen de Kalman (local menos visitante)",
    "game.tech_elo_h": "Descomposición exacta de Elo (solo componente Elo)",
    "game.tech_elo_team": "Diferencial de rating ({home} {hr} vs {away} {ar})",
    "game.tech_elo_hfa": "Factor campo de Elo",
    "game.tech_elo_total": "Margen de Elo (local menos visitante)",
    # model components
    "comp_ensemble_model_only": "Modelo solo (sin mercado)",
    "comp_elo": "Elo con margen de victoria",
    "comp_kf": "Kalman (fuerza dinámica)",
    "comp_lgbm": "LightGBM sin mercado",
    "comp_market": "Mercado (cierre histórico, sin margen)",
    "comp_lgbm_mkt": "LightGBM sobre el mercado",
    "comp_ensemble": "Modelo mezclado con el mercado",
    "model_market": "Mercado (cierre)",
    "model_elo": "Elo (margen de victoria)",
    "model_kf": "Kalman (fuerza dinámica)",
    "model_lgbm": "LightGBM (sin mercado)",
    "model_lgbm_mkt": "LightGBM (residuo frente al mercado)",
    "model_sim": "Simulador (parámetros Kalman)",
    "model_ens": "Modelo mezclado con el mercado",
    # history
    "hist.title": "Historial",
    "hist.lede": "Picks guardados antes del saque: qué dijimos antes de cada partido y qué pasó, sin cambiar nada después.",
    "hist.read_aria": "Resumen del historial",
    "hist.read_hits": "picks acertados",
    "hist.read_pct": "de acierto",
    "hist.rule_h": "Cómo se guarda",
    "hist.rule_1": (
        "Cada pick se guarda en el repositorio antes del saque y no se edita. Solo se califican "
        "los partidos con pick guardado antes de empezar."
    ),
    "hist.rule_2": (
        "Desde la jornada 11 de 2026 el pick oficial es el del modelo solo, sin mezclar con el "
        "mercado. Los picks guardados antes de un cambio se quedan como estaban y se marcan en la "
        "tabla."
    ),
    "hist.rule_3": (
        "El modelo solo, la mezcla con el mercado y el mercado se califican sobre los mismos "
        "partidos, para comparar sin sesgo."
    ),
    "hist.rule_4": (
        "Las jornadas 11 y 12 se publicaron el 17 de noviembre con la mezcla y se volvieron a "
        "guardar el 18 de noviembre con el modelo solo, antes de que se jugara ningún partido."
    ),
    "hist.results_h": "Resultados",
    "hist.col_source": "Fuente",
    "hist.col_hits": "Aciertos",
    "hist.col_pct": "Acierto",
    "hist.src_official": "Pick oficial (el titular de cada fecha)",
    "hist.src_model_only": "Modelo solo, sin mercado",
    "hist.src_ensemble": "Modelo mezclado con el mercado",
    "hist.src_market": "Mercado (al predecir)",
    "hist.kind_model_only": "modelo solo",
    "hist.kind_ensemble": "mezcla con el mercado (anterior)",
    "hist.chart_aria": "Acierto acumulado del pick oficial y del mercado",
    "hist.series_official": "Pick oficial",
    "hist.series_market": "Mercado",
    "hist.chart_note": "Porcentaje de aciertos acumulado, partido a partido. Con pocos partidos la línea salta mucho.",
    "hist.games_h": "Partido a partido",
    "hist.col_date": "Fecha",
    "hist.col_game": "Partido",
    "hist.col_pick": "Pick",
    "hist.col_p": "Probabilidad",
    "hist.col_final": "Final",
    "hist.col_ok": "Resultado",
    "hist.col_kind": "Tipo de pick",
    "hist.empty": "Todavía no hay partidos terminados con pick guardado. Aquí aparecerán el día después de cada partido.",
    "hist.saved_h": "Picks guardados",
    "hist.saved_lede": "Cada jornada, con el momento exacto en que se guardó y el del primer saque.",
    "hist.col_week": "Jornada",
    "hist.col_saved": "Guardado",
    "hist.col_first": "Primer saque",
    "hist.col_n": "Partidos",
    "hist.col_headline": "Número principal",
    "hist.week_n": "Jornada {week}, {season}",
    # calibration chart
    "calib.x": "Probabilidad prevista (%)",
    "calib.y": "Frecuencia real (%)",
    "calib.aria": "Calibración del modelo solo (sin mercado)",
    "table.hint": "Desliza la tabla hacia los lados para ver todas las columnas.",
    # empty
    "empty.title": "Sin jornada todavía",
    "empty.h1": "Sin jornada",
    "empty.lede": "Aún no hay predicciones publicadas. Se generan cada martes por la mañana.",
    # method
    "method.title": "Método",
    "method.lede": "Qué número mostramos, de dónde sale, cómo se mide y, sobre todo, lo que todavía no sabemos hacer.",
    "method.number_h": "El número que mostramos",
    "method.number_1": (
        "La predicción principal es la de nuestro <b>modelo solo</b>: ve estadísticas de los "
        "equipos y del partido, pero no mira las cuotas. El mercado aparece al lado como "
        "referencia y para medir en qué partidos discrepamos."
    ),
    "method.number_2": (
        "Esto tiene un coste y lo decimos: en el histórico, el modelo solo acierta menos y calibra "
        "peor que el mercado. Una mezcla de los dos (el «ensemble» que mostrábamos antes) queda "
        "empatada con el mercado, no por encima. Seguimos guardando la mezcla para comparar."
    ),
    "method.col_source": "Fuente",
    "method.col_acc": "Acierto",
    "method.col_brier": "Brier",
    "method.col_ll": "Log loss",
    "method.col_mae": "Error medio del margen",
    "method.col_ats": "Contra el spread",
    "method.number_table_note": (
        "{n} partidos decididos de temporada regular de {a} a {b} ({played} jugados, {ties} "
        "empates excluidos del scoring probabilístico), semana a semana solo con partidos "
        "anteriores. Brier y log loss: menor es mejor."
    ),
    "method.how_h": "Cómo se calcula",
    "method.how_1": (
        'Partimos de los datos públicos de <a href="https://github.com/nflverse">nflverse</a> '
        "(calendarios, jugada a jugada, partes de lesiones). Cada equipo tiene ratings de ataque "
        "y defensa por EPA (puntos esperados añadidos por jugada) en pase y carrera, ajustados por "
        "la calidad del rival, con memoria que decae y regresión a la media entre temporadas. Todo "
        "se calcula con lo que se sabía antes del partido. Sobre esos ratings corren tres modelos:"
    ),
    "method.how_kf": "<b>Kalman:</b> la fuerza ofensiva y defensiva de cada equipo cambia semana a semana, con incertidumbre explícita.",
    "method.how_lgbm": "<b>LightGBM:</b> árboles pequeños con descanso, viaje, QB, clima y ratings.",
    "method.how_elo": "<b>Elo</b> con margen de victoria.",
    "method.how_stack": (
        "Un ensemble los combina en una probabilidad, un margen y un total, con pesos que se "
        "reajustan cada semana usando solo predicciones anteriores."
    ),
    "method.how_points": (
        "Un simulador de posesiones convierte los puntos esperados de cada equipo en 20.000 "
        "partidos simulados. De ahí salen el rango del 80\u202f% (se descartan el 10\u202f% de los "
        "resultados más bajos y el 10\u202f% de los más altos) y el marcador de ejemplo. El rango es "
        "amplio porque el fútbol americano lo es: dos equipos parejos suelen dar márgenes de "
        "−14 a +14."
    ),
    "method.market_h": "El mercado y las casas de apuestas",
    "method.market_1": (
        "«Mercado» es la probabilidad que implica el consenso de las casas de apuestas que devuelve "
        "The Odds API (regiones de Europa, Reino Unido y EE.\u202fUU., con alguna bolsa de apuestas), "
        "tras quitar el margen de la casa (método de Shin). Si no hay cuotas todavía, es la línea "
        "pre-partido de nflverse (en el backtest histórico 2018-2025 sí es la línea de cierre de nflverse)."
    ),
    "method.market_2": (
        "No mostramos cuotas de casas concretas: la API devuelve operadores de otros países (Francia, "
        "Reino Unido, Suecia, Estados Unidos) y bolsas de apuestas, y no podemos garantizar que "
        "sean las que opera una casa con licencia en España. Por eso solo se enseña el consenso, y "
        "no calculamos valor esperado ni recomendamos apostar."
    ),
    "method.market_3": "La diferencia con el mercado se calcula con los porcentajes tal como los lees: 68\u202f% menos 66\u202f% son 2 puntos.",
    "method.why_h": "La frase de «por qué»",
    "method.why_1": (
        "En los snapshots v1 nuevos, cada ficha muestra dos niveles separados. En la parte visible "
        "aparecen los duelos descriptivos unidad contra unidad (EPA por jugada ajustada por rival "
        "en ataque y EPA permitida por jugada en defensa, con rankings pre-partido 1 a 32 y "
        "desempate alfabético) y el EPA por dropback con memoria exponencial de los quarterbacks "
        "(sin ajuste por rival). El indicador combinado (EPA de ataque más EPA permitida en defensa) "
        "es estrictamente descriptivo, no un efecto causal ni una contribución al margen. En las "
        "primeras jornadas de cada temporada los ratings llevan fuerte encogimiento hacia la media."
    ),
    "method.why_2": (
        "Dentro del detalle técnico se separan cuatro capas sin mezclar modelos distintos: (1) la "
        "agregación exacta del stack del titular (pesos en logit y sesgo para la probabilidad; "
        "pesos NNLS para el margen sobre Elo, Kalman y LightGBM), (2) las contribuciones exactas "
        "TreeSHAP de LightGBM por grupo de variables (solo para LightGBM, nunca para el stack "
        "completo), (3) la descomposición aditiva exacta de Kalman (factor campo más ataque local "
        "frente a defensa visitante menos ataque visitante frente a defensa local) y (4) la "
        "descomposición aditiva de Elo (diferencial de rating más factor campo). Los snapshots "
        "congelados v0 anteriores a este cambio conservan la regla previa sobre entradas."
    ),
    "method.market_4": (
        "Marcamos con filete amarillo las diferencias de 10 puntos o más entre los porcentajes "
        "mostrados. En el histórico 2018-2025 (2133 partidos decididos), esa brecha ocurrió en "
        "506 partidos (23,7\u202f%): el modelo acertó el 59,9\u202f% (IC 95\u202f% por bloques "
        "de 2 semanas: 56,1\u202f% a 63,7\u202f%; log loss 0,673) frente al 65,8\u202f% del "
        "cierre de mercado (61,5\u202f% a 70,2\u202f%; log loss 0,607; diferencia de acierto "
        "-5,9 puntos, IC -11,5 a -0,4). Señala desacuerdo entre lecturas, no una oportunidad."
    ),
    "method.inj_h": "Lesiones",
    "method.inj_1": (
        "Las bajas notables (Out o Doubtful en el parte oficial) se muestran como contexto con el "
        "valor aproximado del jugador, en puntos de margen por partido, medido sobre su reemplazo. "
        "No cambian ninguna cifra de la predicción."
    ),
    "method.inj_2": (
        "Lo probamos de 2018 a 2025 con validación estricta: la mejora fue pequeña y no "
        "significativa con el 95\u202f%, así que no se conectó. El mercado ya descuenta las bajas. "
        "Informe completo:"
    ),
    "method.hist_h": "Resultados históricos",
    "method.hist_1": "Simulación semana a semana de {a} a {b}: {n} partidos decididos ({played} regulares jugados, {ties} empates fuera del scoring probabilístico). Nada del futuro entra.",
    "method.hist_note": (
        "«Contra el spread» es el porcentaje de veces que el lado preferido por el modelo cubre la "
        "línea de cierre; con comisión de −110 hace falta un 52,4\u202f% para no perder dinero."
    ),
    "method.season_h": "Por temporada",
    "method.col_season": "Temporada",
    "method.col_season_mo": "Solo modelo (acierto / LL)",
    "method.col_season_ens": "Mezcla (acierto / LL)",
    "method.col_season_mkt": "Mercado (acierto / LL)",
    "method.season_note": "Cada celda muestra acierto y log loss en los mismos partidos decididos de esa temporada.",
    "method.calib_h": "Calibración",
    "method.calib_1": "Cuando decimos 70\u202f%, ¿gana el 70\u202f% de las veces? Cada punto es un tramo de probabilidad; su tamaño indica cuántos partidos hay. Sobre la diagonal punteada la calibración sería perfecta.",
    "method.calib_2": "Los tramos extremos tienen pocos partidos y se mueven mucho por azar.",
    "method.verdict": (
        "¿Le ganamos a la línea de cierre? No. El modelo solo tiene log loss {mo} frente a {mkt} "
        "del cierre (claramente por detrás en bloques de 1, 2 y 4 semanas). La mezcla ({ens}) "
        "tampoco demuestra ventaja frente al cierre. Informe completo:"
    ),
    "method.verdict_audit": "Auditoría estadística PR 2:",
    "method.verdict_bt": (
        "¿Le ganamos a la línea de cierre? No. La mezcla tiene un log loss de {ens} frente a {mkt} "
        "del cierre: no demuestra ventaja frente al mercado. Tabla completa:"
    ),
    "method.limits_h": "Límites",
    "method.limit_1": "El objetivo realista es un 65 a 70\u202f% de aciertos directos. Nadie con un método público está cerca del 90\u202f%; quien lo promete suele usar datos del futuro sin darse cuenta.",
    "method.limit_2": "No tenemos ventaja demostrada sobre el mercado. Para ganarle hace falta información que él no tenga y probarla fuera de muestra.",
    "method.limit_3": "El QB titular de partidos futuros es el previsto en el calendario. Las bajas solo se conocen con el parte de la semana.",
    "method.limit_4": "El simulador cuenta posesiones, no jugadas: no modela safeties, touchdowns defensivos, reloj, lesiones durante el partido ni clima.",
    "method.limit_5": "Hay pocas temporadas con datos jugada a jugada (desde 2015): los modelos de árboles se sobreajustan con facilidad.",
    "method.gloss_h": "Glosario",
    "method.gloss_brier": "Error cuadrático medio de las probabilidades. Menor es mejor.",
    "method.gloss_ll_t": "Log loss",
    "method.gloss_ll": "Penaliza las probabilidades seguras que fallan. Menor es mejor.",
    "method.gloss_ens_t": "Ensemble",
    "method.gloss_ens": "Combinación de varios modelos con pesos aprendidos de predicciones anteriores.",
    "method.gloss_sim_t": "Simulaciones",
    "method.gloss_sim": "20.000 partidos simulados por posesiones para cada partido real.",
    "method.gloss_pp_t": "Puntos de probabilidad",
    "method.gloss_pp": "Diferencia entre dos porcentajes: de 66\u202f% a 68\u202f% hay 2 puntos.",
    "method.gloss_shin_t": "Sin margen de la casa",
    "method.gloss_shin": "Las cuotas llevan una comisión; se quita para que las probabilidades sumen 100\u202f%.",
    "method.privacy_h": "Privacidad y analítica",
    "method.privacy_off": (
        "En esta compilación la analítica externa está desactivada: la página no carga scripts de "
        "terceros, no realiza peticiones de red salientes (política CSP connect-src 'none') ni "
        "instala cookies de seguimiento."
    ),
    "method.privacy_on": (
        "En esta compilación está activada la medición opt-in de GoatCounter (código {code}). Al "
        "cargar una página, tu navegador envía una petición a gc.zgo.at y a "
        "{code}.goatcounter.com con la ruta visitada, la referencia, el agente de usuario, el "
        "tamaño de ventana y la dirección IP, que GoatCounter utiliza de forma transitoria para "
        "calcular un hash diario de sesión sin guardar cookies."
    ),
    "method.privacy_law": (
        "No usar cookies no equivale a estar exento de obligaciones de privacidad o protección de "
        "datos (como el RGPD): cuando la analítica externa está activada, el navegador transmite "
        "metadatos de petición a un tercero y el responsable del sitio debe informar de ello y "
        "evaluar su base jurídica antes de habilitarla."
    ),
    "method.footer": 'Todo el código y los datos de salida están en <a href="{repo}">{repo}</a> bajo licencia MIT.',
    # Open Graph and SEO metadata
    "og.tagline": "Modelo propio sin mercado. Picks guardados antes del saque.",
    "og.home_title": "Pronósticos NFL",
    "og.home_sub": "Jornada {week}, temporada {season}",
    "og.home_empty": "Sin jornada publicada todavía",
    "og.week_title": "Jornada {week}",
    "og.week_sub": "Temporada NFL {season}",
    "og.games_label": "partidos",
    "og.flags_label": "desacuerdos >= {n} pts",
    "og.featured_label": "PARTIDOS DESTACADOS",
    "og.alt_home": "ensemblitz: pronósticos NFL de la semana actual",
    "og.alt_week": "ensemblitz: pronósticos NFL de la jornada {week}, temporada {season}",
    "og.alt_game": "ensemblitz: {away} en {home}, jornada {week} de {season}",
    "og.alt_history": "ensemblitz: historial de picks guardados antes del saque",
    "og.alt_method": "ensemblitz: método, backtest y límites",
    "og.desc_week": (
        "Pronósticos NFL de la jornada {week} ({season}): probabilidades del modelo sin mercado, "
        "puntos esperados, margen y total."
    ),
    "og.desc_history": (
        "Historial público de picks de la NFL guardados antes del saque, sin editar después."
    ),
    "og.desc_method": (
        "Cómo calcula ensemblitz sus pronósticos NFL, resultados históricos 2018-2025, "
        "calibración y límites."
    ),
    # privacy and local storage
    "privacy.h": "Privacidad y almacenamiento local",
    "privacy.storage": (
        "Este sitio no instala cookies de seguimiento. Solo guarda hasta tres preferencias en el "
        "almacenamiento local de tu navegador (<code>localStorage</code>): <code>ens-theme</code> "
        "(tema claro u oscuro), <code>ens-lang</code> (idioma español o inglés) y "
        "<code>ens-team</code> (tu equipo seguido de la NFL). Esos valores permanecen en tu "
        "dispositivo, no se envían a ningún servidor y puedes borrarlos en cualquier momento "
        "desde los ajustes del navegador."
    ),
    "privacy.hosting": (
        "No usar cookies no equivale a carecer de obligaciones o consideraciones de privacidad. "
        "Las páginas estáticas se sirven desde GitHub Pages, que como proveedor de alojamiento "
        "puede procesar metadatos técnicos estándar de la petición HTTP (como la dirección IP o "
        "el agente de usuario) conforme a la declaración de privacidad de GitHub. El comprobador "
        "SHA-256 de la página de verificación procesa el archivo íntegramente en tu navegador sin "
        "subirlo a ningún servidor."
    ),
    # verify page
    "verify.title": "Verificar",
    "verify.description": (
        "Comprueba la huella SHA-256 de cualquier snapshot publicado frente a "
        "predictions/MANIFEST.json y aprende a verificar las atestaciones en terminal."
    ),
    "verify.lede": (
        "Cada jornada se publica como un archivo JSON inmutable registrado en "
        "predictions/MANIFEST.json. Aquí puedes comprobar su SHA-256 en tu navegador o verificar "
        "la procedencia completa con GitHub CLI."
    ),
    "verify.read_aria": "Resumen de verificación",
    "verify.read_count": "archivos registrados en MANIFEST.json",
    "verify.scope_h": "Qué prueba cada comprobación",
    "verify.scope_browser": (
        "<b>En el navegador (solo SHA-256):</b> esta página calcula únicamente la huella "
        "criptográfica SHA-256 del archivo que selecciones y la compara con la copia incrustada "
        "de <code>predictions/MANIFEST.json</code>. <b>No verifica firmas Sigstore ni "
        "atestaciones de GitHub en el navegador.</b>"
    ),
    "verify.scope_attest": (
        "<b>Con <code>gh attestation verify</code> (integridad y procedencia):</b> las "
        "atestaciones de GitHub y las huellas SHA-256 demuestran integridad del archivo y "
        "procedencia del flujo de publicación (que el archivo fue generado por el workflow del "
        "repositorio y no se alteró después). <b>No demuestran corrección estadística, validez "
        "del modelo ni ventaja predictiva.</b>"
    ),
    "verify.checker_h": "Comprobador local de SHA-256",
    "verify.checker_lede": (
        "Selecciona un archivo <code>.json</code> descargado del repositorio. El cálculo se "
        "ejecuta en tu dispositivo con Web Crypto API (<code>crypto.subtle.digest</code>) y no "
        "realiza ninguna llamada de red."
    ),
    "verify.file_label": "Seleccionar archivo JSON de predicciones",
    "verify.noscript": (
        "Activa JavaScript para calcular el SHA-256 en el navegador, o utiliza los comandos de "
        "terminal que figuran más abajo."
    ),
    "verify.idle": "Elige un archivo JSON para calcular su SHA-256 y compararlo con predictions/MANIFEST.json.",
    "verify.status_match": "Coincide con MANIFEST.json",
    "verify.status_mismatch": "No figura en MANIFEST.json",
    "verify.status_error": "No se pudo calcular el SHA-256",
    "verify.status_unsupported": "Web Crypto API (crypto.subtle) no está disponible en este contexto del navegador.",
    "verify.res_file": "Archivo",
    "verify.res_sha": "SHA-256 calculado",
    "verify.res_paths": "Ruta coincidente",
    "verify.res_match_note": (
        "Huella SHA-256 idéntica a la registrada en predictions/MANIFEST.json. Esta comprobación "
        "en el navegador no verifica firmas Sigstore; usa gh attestation verify para comprobar "
        "la procedencia."
    ),
    "verify.res_mismatch_note": (
        "El SHA-256 calculado no coincide con ningún archivo de la copia incrustada de "
        "predictions/MANIFEST.json."
    ),
    "verify.cli_h": "Verificación completa en terminal (gh attestation verify)",
    "verify.cli_lede": (
        "Para comprobar las firmas criptográficas Sigstore y la procedencia de GitHub Actions, "
        "descarga el archivo y ejecuta GitHub CLI tanto sobre el manifiesto como sobre el "
        "snapshot concreto:"
    ),
    "verify.cli_manifest_label": "1. Verificar el manifiesto (predictions/MANIFEST.json):",
    "verify.cli_snapshot_label": "2. Verificar un snapshot individual:",
    "verify.cli_note": "Procedimiento completo del registro inmutable en",
    "verify.manifest_h": "Snapshots registrados en predictions/MANIFEST.json",
    "verify.manifest_lede": "Listado completo de rutas y huellas SHA-256 publicadas en el repositorio.",
    "verify.col_path": "Archivo",
    "verify.col_sha": "SHA-256",
    "verify.col_link": "Repositorio",
    "verify.view_gh": "Ver en GitHub",
    "verify.empty": "Todavía no hay archivos registrados en predictions/MANIFEST.json.",
}

EN: dict[str, str] = {
    "na": "n/a",
    "even": "even",
    "tie": "tie",
    "night_thu": "Thursday night",
    "night_mon": "Monday night",
    "night_sun": "Sunday night",
    "status_out": "Out",
    "status_doubtful": "Doubtful",
    "status_questionable": "Questionable",
    "status_returning": "Returning",
    "status_other": "Update",
    "site.title": "NFL predictions",
    "site.description": (
        "Who wins each NFL game, by how much and how many points to expect, from our own model "
        "set against the betting market. Picks are saved before kickoff."
    ),
    "nav.skip": "Skip to content",
    "nav.home_aria": "ensemblitz, home",
    "nav.aria": "Sections",
    "nav.week": "Week",
    "nav.history": "Record",
    "nav.method": "Method",
    "nav.verify": "Verify",
    "nav.code": "Code",
    "nav.data_of": "Data from {when}",
    "nav.lang_aria": "Leer esta página en español",
    "nav.theme_aria": "Switch between light and dark theme",
    "foot.generated": "Latest picks saved {when}. Picks are saved before kickoff and never edited.",
    "foot.license": "MIT license. Data from nflverse under CC-BY 4.0. Typefaces Archivo and IBM Plex Mono under the SIL OFL.",
    "week.title": "Week {week}",
    "week.h1": "Week {week}",
    "week.lede": (
        "{season} NFL season: win probabilities, expected points and margins from our own "
        "statistical model without betting odds, saved before kickoff. Every forecast sits beside "
        "the market as a reference; all times ET."
    ),
    "week.read_aria": "Week summary",
    "week.read_games": "games this week",
    "week.read_flags": "games where we differ from the market",
    "week.read_next": "{away} at {home}",
    "week.read_next_live": "until {away} at {home}",
    "week.read_hits": "picks correct",
    "week.nav": "Weeks",
    "week.nav_aria": "Weeks",
    "week.nav_item": "Week {w}",
    "week.legend": (
        "Expected points per team and, in brackets, the range covering 80% of the simulated "
        "outcomes."
    ),
    "week.legend_flag": "Yellow bar: our probability is {n} points or more away from the market's (a reading gap, not an edge).",
    "week.legacy": (
        "Some games this week were saved before the model change and show the pick of that time, "
        "which blended the model with the market. Each one says so."
    ),
    "filter.label": "Filter games",
    "filter.all": "All",
    "filter.flags": "Where we differ from the market",
    "filter.team": "My team",
    "filter.empty": "No games match the active filters.",
    "team.label": "Follow team",
    "team.none": "None",
    "cols.time": "Time",
    "cols.game": "Game",
    "cols.win": "Winner",
    "cols.points": "Expected points",
    "cols.margin": "Margin",
    "cols.total": "Total",
    "day.games_one": "{n} game",
    "day.games_n": "{n} games",
    "day.night": "{night}",
    "notes.aria": "Notes",
    "notes.saved": "Picks saved {when}.",
    "notes.market_books": '"Market" is the aggregate consensus from The Odds API (margin removed).',
    "notes.market_nflverse": '"Market" is the pre-game nflverse line (margin removed).',
    "notes.method": "How we measure it.",
    "notes.disclaimer": "This is a statistics exercise, not betting advice.",
    "card.at": "at",
    "card.wins": "{team} wins",
    "card.win_aria": "{team} wins with a probability of {p}",
    "card.market": "Market: {p} (us {d})",
    "card.market_flagged": "Market: {p}",
    "card.final": "Final: {away} {a}, {home} {h}.",
    "card.hit": "Pick correct.",
    "card.miss": "Pick missed.",
    "card.hit_short": "Hit",
    "card.miss_short": "Miss",
    "card.absences": "Notable absences: {list}.",
    "card.absence_item": "{player} ({team}, {status}, {pts} pts)",
    "card.absences_note": "Context: not included in the number.",
    "card.band_happened": "This happened.",
    "card.band_outside": "The result landed outside these three.",
    "band.away_15": "{team} by 15 or more",
    "band.away_8_14": "{team} by 8 to 14",
    "band.away_1_7": "{team} by 1 to 7",
    "band.tie": "Tie",
    "band.home_1_7": "{team} by 1 to 7",
    "band.home_8_14": "{team} by 8 to 14",
    "band.home_15": "{team} by 15 or more",
    "game.bands_h": "Most likely margins",
    "game.bands_note": "The three margins with the most weight in the score simulation. A tie is its own band.",
    "news.title": "Latest news",
    "news.note": "Context: not applied to the forecast figures.",
    "news.source": "source",
    "game.description": "{away} at {home}: {fav} wins with {p}. Expected points, margin, total and context.",
    "game.week_ctx": "Week {week}, {season} season.",
    "game.tz_note": "ET",
    "game.read_aria": "Game summary",
    "game.margin_of": "margin, {txt}",
    "game.total_label": "total points",
    "game.market_label": "market probability",
    "game.legacy": (
        "This game was saved before the model change: its pick blended the model with the market "
        "and has no per-team ranges."
    ),
    "game.points_h": "Expected points",
    "game.col_team": "Team",
    "game.col_exp": "Expected",
    "game.col_range": "80% range",
    "game.row_margin": "Margin",
    "game.row_total": "Total",
    "game.margin_range": "{lo} to {hi}",
    "game.range_note": "The range leaves out the lowest 10% and the highest 10% of the simulated outcomes.",
    "game.example": (
        "An example score: {away} {a}, {home} {h}. It is one of many possible scores and none "
        "reaches 2% probability."
    ),
    "game.market_h": "Against the market",
    "game.ours": "Our model",
    "game.market": "Market",
    "game.diff": "Difference",
    "game.market_src_label": "Source",
    "game.market_src_odds_api": "The Odds API consensus ({n} operators, margin removed)",
    "game.market_src_nflverse_pre": "Pre-game nflverse line (margin removed)",
    "game.market_src_nflverse_close": "Historical nflverse line (margin removed)",
    "game.market_time_fetched": "Fetched {when} (The Odds API cache).",
    "game.market_time_captured": "Captured {when} (quote snapshot).",
    "game.market_time_read": "Read {when} (at prediction generation).",
    "game.ref_line_h": "Reference line (nflverse)",
    "game.line": "Spread and total",
    "game.line_total": "total {v}",
    "game.ref_line_note": "From the pre-game nflverse schedule; a separate source from The Odds API win-probability consensus.",
    "game.market_src_books": "The market is the consensus of {n} operators (The Odds API), with their margin removed.",
    "game.market_src_nflverse": "The market is the pre-game nflverse line, with its margin removed.",
    "game.market_note": "It is only a reference: we do not use its numbers to compute ours.",
    "game.flag_text": (
        "The model gives {fav} {ours} and the market {mkt}: a gap of {d} points. In 2018-2025, on "
        "gaps of {n} points or more (506 of 2,133 games), the model was right 59.9% of the time "
        "(95% CI: 56.1% to 63.7%) against 65.8% for the historical market (61.5% to 70.2%). This "
        "mark flags a reading disagreement, not an edge."
    ),
    "game.close_text": "The model gives {fav} {ours} and the market {mkt}: similar readings.",
    "game.context_h": "Context",
    "game.absences_h": "Notable absences",
    "game.absence": "{player} ({team}): {status}. Approximate value: {pts} points of margin per game.",
    "game.absences_note": (
        "This is context and is not part of the numbers above. The points estimate the player's "
        "value over a replacement. In 2018 to 2025 tests, adjusting the number for injuries did "
        "not improve the forecast significantly."
    ),
    "game.dist_h": "How much it can vary",
    "game.chart_margin": "Simulated margin (home minus away)",
    "game.chart_total": "Simulated total points",
    "game.dist_note": "Each bar is the frequency of one outcome among thousands of simulated games.",
    "game.tech_h": "Technical detail",
    "game.tech_src": "Source",
    "game.tech_prob": "{team} probability",
    "game.tech_note": "The first three models make up the headline number. LightGBM on top of the market and the blend take the pre-game nflverse reference as input.",
    "game.back": "Back to week {week}",
    "game.copy_link": "Copy link",
    "game.copied": "Link copied",
    "game.copy_fail": "Could not copy link",
    "fact.rest": "Rest",
    "fact.rest_v": "{home} {h} days, {away} {a} days",
    "fact.trip": "Visitor's trip",
    "fact.trip_v": "{away}, {km} km",
    "fact.qb": "Starting QB",
    "fact.qb_change": "starter changed for {teams}",
    "fact.qb_same": "no change since the last game",
    "fact.venue": "Stadium",
    "fact.venue_dome": "Dome or closed roof",
    "fact.venue_open": "Outdoors, {temp}, wind {wind}",
    "fact.venue_open_nowx": "Outdoors. The forecast weather is not in the model yet",
    "chart.line": "nflverse {v}",
    "chart.wins": "{team} wins",
    "chart.points": "total points",
    "chart.margin_aria": "Distribution of the simulated margin (home minus away)",
    "chart.total_aria": "Distribution of the simulated total points",
    "why_qb": "The biggest factor: {team} start a different quarterback than in their last game.",
    "why_rest": "The biggest factor: {team} come in with {n} days of rest and their opponent with {m}.",
    "why_trip": "The biggest factor: {team} travel {km} km to visit {home}.",
    "why_wind": "The biggest factor: wind of {wind}, which cuts down the passing game.",
    "why_home": "A close game: home-field advantage tilts the pick towards {team}.",
    "why_away_close": "A close game: {team} are slightly better, even on the road.",
    "why_form": "The biggest factor: recent form. The model sees {team} clearly ahead of {other}.",
    "why_v1": (
        "Biggest unit mismatch: {off} {unit} offense (#{off_rank}) vs {dfn} {unit} defense "
        "(#{def_rank}). The largest share of the model margin comes from {comp}."
    ),
    "why_v1_qb": (
        "Starting QB change for {qb_teams}. Biggest unit mismatch: {off} {unit} offense "
        "(#{off_rank}) vs {dfn} {unit} defense (#{def_rank}); largest margin share from {comp}."
    ),
    "unit_pass": "pass",
    "unit_rush": "rush",
    "comp_short_elo": "Elo",
    "comp_short_kf": "Kalman",
    "comp_short_lgbm": "LightGBM",
    "game.matchups_h": "Matchups to watch",
    "game.m_col_unit": "Matchup",
    "game.m_col_off": "Offense (EPA/play)",
    "game.m_col_def": "Defense allowed",
    "game.m_col_comp": "Comparison",
    "game.m_row": "{unit}: {off} vs {dfn}",
    "game.m_rank_val": "#{rank} ({val})",
    "game.m_favors": "Tilts to {team} ({val})",
    "game.m_note": (
        "Opponent-adjusted EPA per play on offense (higher is better) and opponent-adjusted EPA "
        "allowed per play on defense (lower is better), with pre-game league ranks 1 to 32 "
        "(alphabetical tie-breaking). The comparison adds offense EPA and defense EPA allowed: it "
        "is a descriptive indicator only, not a causal effect or a predicted margin contribution."
    ),
    "game.m_early_note": (
        "Early season (week {week}): pre-game ratings combine limited recent plays with heavy "
        "prior shrinkage toward the league average."
    ),
    "game.qb_h": "Quarterbacks (EPA per dropback)",
    "game.qb_row": "{team}",
    "game.qb_val": "{epa} EPA/dropback ({db} decayed dropbacks)",
    "game.qb_diff_label": "Difference (home minus away)",
    "game.qb_note": (
        "Time-decayed EPA per dropback for the scheduled starter (pre-game nflverse play-by-play, "
        "not opponent-adjusted)."
    ),
    "game.absences_cutoff": (
        "Contextual diagnostic from nflverse (cutoff {when}); not included in any probability or margin."
    ),
    "game.tech_stack_h": "Exact headline stack aggregation (no-market stack)",
    "game.tech_stack_col_pw": "Logit weight",
    "game.tech_stack_col_lc": "Logit term",
    "game.tech_stack_col_mw": "Margin weight",
    "game.tech_stack_col_mc": "Margin term",
    "game.tech_stack_bias": "Logit bias (Platt)",
    "game.tech_stack_note": (
        "Headline win probability = sigmoid(sum of logit terms + bias). Headline margin = sum of "
        "margin terms (home minus away)."
    ),
    "game.tech_lgbm_h": "LightGBM TreeSHAP attributions (LightGBM component only)",
    "game.tech_lgbm_col_grp": "Feature group",
    "game.tech_lgbm_col_val": "LightGBM margin term",
    "game.tech_lgbm_base": "LightGBM base margin",
    "game.tech_lgbm_pred": "LightGBM predicted margin",
    "game.tech_lgbm_note": (
        "Exact TreeSHAP decomposition of the no-market LightGBM component (home minus away). It "
        "does not explain the complete stack and does not redistribute Kalman or Elo weights."
    ),
    "grp_pass_game": "Passing game (pass EPA)",
    "grp_rush_game": "Rushing game (rush EPA)",
    "grp_efficiency": "Success rate",
    "grp_qb": "Quarterback (EPA/dropback and changes)",
    "grp_team_strength": "Prior team strength (Kalman and Elo)",
    "grp_situational": "Situational (rest, travel, venue, weather)",
    "game.tech_kf_h": "Exact Kalman decomposition (Kalman component only)",
    "game.tech_kf_hfa": "Kalman home-field advantage",
    "game.tech_kf_h_vs_a": "{home} offense + {away} defense allowed",
    "game.tech_kf_a_vs_h": "Minus ({away} offense + {home} defense allowed)",
    "game.tech_kf_total": "Kalman margin (home minus away)",
    "game.tech_elo_h": "Exact Elo decomposition (Elo component only)",
    "game.tech_elo_team": "Rating gap ({home} {hr} vs {away} {ar})",
    "game.tech_elo_hfa": "Elo home-field advantage",
    "game.tech_elo_total": "Elo margin (home minus away)",
    "comp_ensemble_model_only": "Model only (no market)",
    "comp_elo": "Elo with margin of victory",
    "comp_kf": "Kalman (dynamic strength)",
    "comp_lgbm": "LightGBM without market",
    "comp_market": "Market (historical closing, margin removed)",
    "comp_lgbm_mkt": "LightGBM on top of the market",
    "comp_ensemble": "Model blended with the market",
    "model_market": "Market (closing)",
    "model_elo": "Elo (margin of victory)",
    "model_kf": "Kalman (dynamic strength)",
    "model_lgbm": "LightGBM (no market)",
    "model_lgbm_mkt": "LightGBM (residual on the market)",
    "model_sim": "Simulator (Kalman parameters)",
    "model_ens": "Model blended with the market",
    "hist.title": "Record",
    "hist.lede": "Picks saved before kickoff: what we said before each game and what happened, with nothing changed afterwards.",
    "hist.read_aria": "Record summary",
    "hist.read_hits": "picks correct",
    "hist.read_pct": "accuracy",
    "hist.rule_h": "How picks are saved",
    "hist.rule_1": (
        "Every pick is saved in the repository before kickoff and never edited. Only games with a "
        "pick saved before they started are graded."
    ),
    "hist.rule_2": (
        "From week 11 of 2026 the official pick is the model on its own, with no market blending. "
        "Picks saved before a change stay as they were and are marked in the table."
    ),
    "hist.rule_3": (
        "The model alone, the blend with the market and the market are graded on the same games, "
        "so they compare fairly."
    ),
    "hist.rule_4": (
        "Weeks 11 and 12 were published on 17 November with the blend and saved again on "
        "18 November with the model alone, before any game was played."
    ),
    "hist.results_h": "Results",
    "hist.col_source": "Source",
    "hist.col_hits": "Correct",
    "hist.col_pct": "Accuracy",
    "hist.src_official": "Official pick (the headline at the time)",
    "hist.src_model_only": "Model alone, no market",
    "hist.src_ensemble": "Model blended with the market",
    "hist.src_market": "Market (at prediction time)",
    "hist.kind_model_only": "model alone",
    "hist.kind_ensemble": "blend with the market (earlier)",
    "hist.chart_aria": "Running accuracy of the official pick and the market",
    "hist.series_official": "Official pick",
    "hist.series_market": "Market",
    "hist.chart_note": "Running share of correct picks, game by game. With few games the line jumps a lot.",
    "hist.games_h": "Game by game",
    "hist.col_date": "Date",
    "hist.col_game": "Game",
    "hist.col_pick": "Pick",
    "hist.col_p": "Probability",
    "hist.col_final": "Final",
    "hist.col_ok": "Result",
    "hist.col_kind": "Pick type",
    "hist.empty": "No finished games with a saved pick yet. They will appear here the day after each game.",
    "hist.saved_h": "Saved picks",
    "hist.saved_lede": "Every week, with the exact time it was saved and the first kickoff.",
    "hist.col_week": "Week",
    "hist.col_saved": "Saved",
    "hist.col_first": "First kickoff",
    "hist.col_n": "Games",
    "hist.col_headline": "Headline number",
    "hist.week_n": "Week {week}, {season}",
    "calib.x": "Predicted probability (%)",
    "calib.y": "Observed frequency (%)",
    "calib.aria": "Calibration of the model on its own (no market)",
    "table.hint": "Swipe the table sideways to see all columns.",
    "empty.title": "No week yet",
    "empty.h1": "No week yet",
    "empty.lede": "No predictions have been published yet. They are generated every Tuesday morning.",
    "method.title": "Method",
    "method.lede": "Which number we show, where it comes from, how it is measured and, above all, what we cannot do yet.",
    "method.number_h": "The number we show",
    "method.number_1": (
        "The headline prediction is our <b>model on its own</b>: it sees team and game statistics "
        "but not the odds. The market sits next to it as a reference and to show where we "
        "disagree."
    ),
    "method.number_2": (
        "This has a cost and we say so: in the record, the model alone is less accurate and less "
        'well calibrated than the market. A blend of the two (the "ensemble" we showed before) '
        "ties with the market, it does not beat it. We keep saving the blend for comparison."
    ),
    "method.col_source": "Source",
    "method.col_acc": "Accuracy",
    "method.col_brier": "Brier",
    "method.col_ll": "Log loss",
    "method.col_mae": "Mean margin error",
    "method.col_ats": "Against the spread",
    "method.number_table_note": (
        "{n} decided regular-season games from {a} to {b} ({played} played, {ties} ties excluded "
        "from probabilistic scoring), week by week using earlier games only. Brier and log loss: "
        "lower is better."
    ),
    "method.how_h": "How it is computed",
    "method.how_1": (
        'We start from the public data of <a href="https://github.com/nflverse">nflverse</a> '
        "(schedules, play by play, injury reports). Each team has attack and defence ratings from "
        "EPA (expected points added per play) in passing and rushing, adjusted for opponent "
        "quality, with decaying memory and regression to the mean between seasons. Everything is "
        "computed from what was known before the game. Three models run on those ratings:"
    ),
    "method.how_kf": "<b>Kalman:</b> each team's offensive and defensive strength changes week to week, with explicit uncertainty.",
    "method.how_lgbm": "<b>LightGBM:</b> small trees using rest, travel, QB, weather and ratings.",
    "method.how_elo": "<b>Elo</b> with margin of victory.",
    "method.how_stack": (
        "An ensemble combines them into a probability, a margin and a total, with weights refitted "
        "every week using earlier predictions only."
    ),
    "method.how_points": (
        "A possession simulator turns each team's expected points into 20,000 simulated games. "
        "The 80% range (the lowest 10% and the highest 10% of outcomes are dropped) and the "
        "example score come from there. The range is wide because football is: two even teams "
        "often produce margins from −14 to +14."
    ),
    "method.market_h": "The market and sportsbooks",
    "method.market_1": (
        '"Market" is the probability implied by the consensus of the sportsbooks returned by '
        "The Odds API (Europe, the UK and the US regions, with some betting exchanges), with the "
        "bookmaker's margin removed (Shin's method). When there are no odds yet, it is the pre-game "
        "nflverse line (in the 2018-2025 historical backtest it is the nflverse closing line)."
    ),
    "method.market_2": (
        "We do not show prices from individual sportsbooks: the API returns operators from other "
        "countries (France, the UK, Sweden, the US) and betting exchanges, and we cannot guarantee "
        "they are the ones a Spanish-licensed operator offers. So only the consensus is shown, and "
        "we compute no expected value and do not recommend bets."
    ),
    "method.market_3": "The difference from the market uses the percentages as you read them: 68% minus 66% is 2 points.",
    "method.why_h": 'The "why" sentence',
    "method.why_1": (
        "In new v1 snapshots, each game page has two separate levels. Visible by default are the "
        "descriptive unit-vs-unit matchups (opponent-adjusted EPA per play on offense and "
        "opponent-adjusted EPA allowed per play on defense, with pre-game ranks 1 to 32 and "
        "alphabetical tie-breaking) and decayed quarterback EPA per dropback (not "
        "opponent-adjusted). The combined indicator (offense EPA plus defense EPA allowed) is "
        "strictly descriptive, not a causal effect or a predicted margin contribution. Early in "
        "each season, ratings carry heavy prior shrinkage toward the league mean."
    ),
    "method.why_2": (
        "Inside technical detail, four layers stay strictly separate without merging distinct "
        "models: (1) the exact headline stack aggregation (logit weights and bias for win "
        "probability; NNLS margin weights over Elo, Kalman and LightGBM), (2) exact LightGBM "
        "TreeSHAP feature-group attributions (LightGBM component only, never the full stack), "
        "(3) Kalman's exact additive margin decomposition (home-field advantage plus home offense "
        "vs away defense minus away offense vs home defense), and (4) Elo's exact additive margin "
        "decomposition (rating gap plus Elo home-field advantage). Frozen v0 snapshots written "
        "before this change keep the earlier input-rule summary."
    ),
    "method.market_4": (
        "A yellow bar marks gaps of 10 percentage points or more between printed probabilities. "
        "In the 2018-2025 record (2,133 decided games), that occurred in 506 games (23.7%): the "
        "model was right 59.9% of the time (2-week block 95% CI: 56.1% to 63.7%; log loss 0.673) "
        "against 65.8% for the closing market (61.5% to 70.2%; log loss 0.607; accuracy gap "
        "-5.9 points, 95% CI -11.5 to -0.4). It flags a reading gap, not a profitable edge."
    ),
    "method.inj_h": "Injuries",
    "method.inj_1": (
        "Notable absences (Out or Doubtful on the official report) are shown as context with the "
        "player's approximate value, in points of margin per game over a replacement. They do not "
        "change any forecast figure."
    ),
    "method.inj_2": (
        "We tested it over 2018 to 2025 with strict validation: the improvement was small and not "
        "significant at 95%, so it was not wired in. The market already prices absences in. Full "
        "report:"
    ),
    "method.hist_h": "Historical results",
    "method.hist_1": "Week-by-week simulation from {a} to {b}: {n} decided games ({played} regular-season games played, {ties} ties excluded from probabilistic scoring). Nothing from the future gets in.",
    "method.hist_note": (
        '"Against the spread" is how often the side the model prefers covers the closing line; '
        "with −110 juice you need 52.4% to break even."
    ),
    "method.season_h": "By season",
    "method.col_season": "Season",
    "method.col_season_mo": "Model only (acc / LL)",
    "method.col_season_ens": "Blend (acc / LL)",
    "method.col_season_mkt": "Market (acc / LL)",
    "method.season_note": "Each cell shows accuracy and log loss on the same decided games of that season.",
    "method.calib_h": "Calibration",
    "method.calib_1": "When we say 70%, does the team win 70% of the time? Each dot is a probability bucket; its size shows how many games it holds. On the dotted diagonal calibration would be perfect.",
    "method.calib_2": "The extreme buckets hold few games and move a lot by chance.",
    "method.verdict": (
        "Do we beat the closing line? No. The model alone has a log loss of {mo} against {mkt} "
        "for the closing line (clearly behind across 1-, 2- and 4-week blocks). The blend ({ens}) "
        "shows no robust edge over the closing line either. Full report:"
    ),
    "method.verdict_audit": "PR 2 statistical audit:",
    "method.verdict_bt": (
        "Do we beat the closing line? No. The blend has a log loss of {ens} against {mkt} for the "
        "closing line: no demonstrated edge over the market. Full table:"
    ),
    "method.limits_h": "Limits",
    "method.limit_1": "A realistic target is 65 to 70% straight-up accuracy. Nobody with a public method is near 90%; whoever promises it is usually using future data without noticing.",
    "method.limit_2": "We have no demonstrated edge over the market. Beating it takes information it lacks, proven out of sample.",
    "method.limit_3": "The starting QB of future games is the one expected on the schedule. Absences are only known from the week's report.",
    "method.limit_4": "The simulator counts possessions, not plays: it does not model safeties, defensive touchdowns, the clock, in-game injuries or weather.",
    "method.limit_5": "Few seasons have play-by-play data (since 2015): tree models overfit easily.",
    "method.gloss_h": "Glossary",
    "method.gloss_brier": "Mean squared error of the probabilities. Lower is better.",
    "method.gloss_ll_t": "Log loss",
    "method.gloss_ll": "Punishes confident probabilities that miss. Lower is better.",
    "method.gloss_ens_t": "Ensemble",
    "method.gloss_ens": "A combination of several models with weights learned from earlier predictions.",
    "method.gloss_sim_t": "Simulations",
    "method.gloss_sim": "20,000 possession-by-possession games simulated for every real game.",
    "method.gloss_pp_t": "Points of probability",
    "method.gloss_pp": "The difference between two percentages: from 66% to 68% is 2 points.",
    "method.gloss_shin_t": "Margin removed",
    "method.gloss_shin": "Odds carry a bookmaker fee; it is taken out so the probabilities add up to 100%.",
    "method.privacy_h": "Privacy and analytics",
    "method.privacy_off": (
        "External analytics is disabled in this build: the page loads no third-party scripts, "
        "makes no outbound network requests (CSP connect-src 'none'), and sets no tracking "
        "cookies."
    ),
    "method.privacy_on": (
        "Opt-in GoatCounter measurement is enabled in this build (code {code}). When a page "
        "loads, your browser sends a request to gc.zgo.at and {code}.goatcounter.com with the "
        "page path, referrer, user agent, viewport size and IP address, which GoatCounter uses "
        "transiently to compute a daily session hash without setting cookies."
    ),
    "method.privacy_law": (
        "Using no cookies does not mean zero privacy or data-protection obligations (such as "
        "under the GDPR): when external analytics is enabled, the browser transmits request "
        "metadata to a third-party processor, and the site operator remains responsible for "
        "transparency notices and legal-basis assessment before turning it on."
    ),
    "method.footer": 'All the code and output data are at <a href="{repo}">{repo}</a> under the MIT license.',
    # Open Graph and SEO metadata
    "og.tagline": "Model on its own, no market. Picks saved before kickoff.",
    "og.home_title": "NFL predictions",
    "og.home_sub": "Week {week}, {season} season",
    "og.home_empty": "No week published yet",
    "og.week_title": "Week {week}",
    "og.week_sub": "{season} NFL season",
    "og.games_label": "games",
    "og.flags_label": "gaps >= {n} pts",
    "og.featured_label": "FEATURED GAMES",
    "og.alt_home": "ensemblitz: current week NFL predictions",
    "og.alt_week": "ensemblitz: Week {week} NFL predictions, {season} season",
    "og.alt_game": "ensemblitz: {away} at {home}, Week {week}, {season}",
    "og.alt_history": "ensemblitz: record of picks saved before kickoff",
    "og.alt_method": "ensemblitz: method, backtest and limits",
    "og.desc_week": (
        "Week {week} ({season}) NFL predictions: model-only win probabilities, expected points, "
        "margin and total."
    ),
    "og.desc_history": (
        "Public record of NFL picks saved before kickoff and never edited afterwards."
    ),
    "og.desc_method": (
        "How ensemblitz computes its NFL predictions, 2018-2025 historical results, calibration "
        "and limits."
    ),
    "privacy.h": "Privacy and local storage",
    "privacy.storage": (
        "This site sets no tracking cookies. It only stores up to three preferences in your "
        "browser's local storage (<code>localStorage</code>): <code>ens-theme</code> (light or "
        "dark theme), <code>ens-lang</code> (Spanish or English language) and "
        "<code>ens-team</code> (your followed NFL team). Those values stay on your device, are "
        "never sent to any server, and can be cleared at any time in your browser settings."
    ),
    "privacy.hosting": (
        "Using zero cookies does not mean zero privacy obligations or considerations. The static "
        "pages are hosted on GitHub Pages, which as hosting infrastructure may process standard "
        "HTTP request metadata (such as IP address or user agent) under GitHub's privacy "
        "statement. The SHA-256 checker on the verification page hashes the chosen file strictly "
        "inside your browser without uploading it to any server."
    ),
    "verify.title": "Verify",
    "verify.description": (
        "Check the SHA-256 digest of any published snapshot against predictions/MANIFEST.json "
        "and verify GitHub attestations from the command line."
    ),
    "verify.lede": (
        "Every week is published as an immutable JSON snapshot indexed in "
        "predictions/MANIFEST.json. Check its SHA-256 locally in your browser or verify full "
        "provenance with the GitHub CLI."
    ),
    "verify.read_aria": "Verification summary",
    "verify.read_count": "artifacts indexed in MANIFEST.json",
    "verify.scope_h": "What each check proves",
    "verify.scope_browser": (
        "<b>In the browser (SHA-256 only):</b> this page computes only the SHA-256 digest of the "
        "file you pick and compares it against the embedded copy of "
        "<code>predictions/MANIFEST.json</code>. <b>It does not verify Sigstore signatures or "
        "GitHub attestations in the browser.</b>"
    ),
    "verify.scope_attest": (
        "<b>With <code>gh attestation verify</code> (integrity and provenance):</b> GitHub "
        "attestations and SHA-256 digests prove artifact integrity and workflow provenance (that "
        "the file was generated by the repository workflow and left unaltered afterward). "
        "<b>They do not prove statistical correctness, model validity, or predictive edge.</b>"
    ),
    "verify.checker_h": "Local SHA-256 checker",
    "verify.checker_lede": (
        "Pick a <code>.json</code> snapshot downloaded from the repository. Hashing runs locally "
        "on your device using the Web Crypto API (<code>crypto.subtle.digest</code>) with zero "
        "network requests."
    ),
    "verify.file_label": "Select prediction JSON file",
    "verify.noscript": (
        "Enable JavaScript to compute SHA-256 in the browser, or use the command-line "
        "instructions below."
    ),
    "verify.idle": "Choose a JSON file to compute its SHA-256 and compare it against predictions/MANIFEST.json.",
    "verify.status_match": "Matches MANIFEST.json",
    "verify.status_mismatch": "Not found in MANIFEST.json",
    "verify.status_error": "Could not compute SHA-256",
    "verify.status_unsupported": "Web Crypto API (crypto.subtle) is not available in this browser context.",
    "verify.res_file": "File",
    "verify.res_sha": "Computed SHA-256",
    "verify.res_paths": "Matching path",
    "verify.res_match_note": (
        "SHA-256 digest matches the entry recorded in predictions/MANIFEST.json. This browser "
        "check does not verify Sigstore signatures; use gh attestation verify to check workflow "
        "provenance."
    ),
    "verify.res_mismatch_note": (
        "The computed SHA-256 does not match any artifact in the embedded copy of "
        "predictions/MANIFEST.json."
    ),
    "verify.cli_h": "Full command-line verification (gh attestation verify)",
    "verify.cli_lede": (
        "To verify cryptographic Sigstore signatures and GitHub Actions provenance, download the "
        "files and run the GitHub CLI on both the manifest and the specific snapshot:"
    ),
    "verify.cli_manifest_label": "1. Verify the manifest (predictions/MANIFEST.json):",
    "verify.cli_snapshot_label": "2. Verify an individual snapshot:",
    "verify.cli_note": "Full append-only ledger procedure in",
    "verify.manifest_h": "Snapshots indexed in predictions/MANIFEST.json",
    "verify.manifest_lede": "Complete index of published paths and SHA-256 digests in the repository.",
    "verify.col_path": "Artifact",
    "verify.col_sha": "SHA-256",
    "verify.col_link": "Repository",
    "verify.view_gh": "View on GitHub",
    "verify.empty": "No artifacts are indexed in predictions/MANIFEST.json yet.",
}

STRINGS = {"es": ES, "en": EN}
