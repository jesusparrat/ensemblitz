# Fase 1: impacto de lesiones por jugador

Generado el 2026-11-18T21:24:15+00:00. 2133 partidos de temporada regular (2018 a 2025), walk-forward estricto: valor del jugador, probabilidad de jugar, coeficientes de cada grupo, tabla de márgenes y desviación típica se calculan antes de cada semana solo con semanas anteriores. Datos en `reports/phase1_injuries.json`; lo genera `ensemblitz phase1`, no se edita a mano.

**Veredicto: las lesiones mejoran un poco la estimación, pero no de forma significativa con el 95 %. No se conecta a producción.** El intervalo del log loss es [−0,0056; +0,0000] y llega a tocar el cero.

## Conclusiones en lenguaje llano

1. **Efecto de las lesiones (comparación principal, fijada antes de mirar).** Mismo margen del modelo sin mercado y misma conversión a probabilidad, con y sin el ajuste por lesiones: log loss −0,0028 (IC 95 % [−0,0056; +0,0000]), Brier −0,0013 ([−0,0025; +0,0000]). El error del margen baja 1,36 puntos² (IC [−2,84; +0,03]). 
2. **Hay señal real, pero pequeña.** El ajuste medio es de 0,8 puntos de spread por partido y solo 175 partidos pasan de 2 puntos. Un punto de spread vale unos 3 puntos de probabilidad de victoria, así que casi nunca cambia el ganador previsto. Con un solo coeficiente para todas las lesiones (exploratorio) el efecto es −0,0030 ([−0,0058; −0,0002]); el coeficiente total vale 0,60 ± 0,12 en el ajuste de toda la muestra. Esa variante se probó después de ver el resultado principal, así que no se usa para decidir.
3. **Seguimos lejos del mercado.** El candidato con lesiones tiene +0,0208 de log loss frente al cierre (IC [+0,0136; +0,0281]). Las lesiones cierran una parte pequeña de la distancia, no la mayoría.
4. **Contra el spread no cambia nada.** ATS del margen sin lesiones: 1024-1057-52 (49,2 %); con lesiones: 1018-1063-52 (48,9 %). Ambos por debajo del 52,38 % de equilibrio.
5. **El mercado ya descuenta las lesiones.** Al explicar lo que el spread de cierre se deja (resultado menos spread) con las mismas cargas de lesiones, el coeficiente total es 0,17 ± 0,12: indistinguible de cero. Las lesiones ayudan a un modelo que no mira el mercado porque el mercado ya las usa.
6. **La tabla discreta de márgenes no mejora la probabilidad de victoria.** Frente a la curva normal el log loss cambia −0,0001 ([−0,0003; +0,0001]). Los números clave importan para la probabilidad de cubrir un spread, no para quién gana. Y la tabla todavía no cubre bien ese caso: con línea de 3,5 da 46,4 % de cubrir y los favoritos reales cubrieron 49,6 %. No debe usarse para cubrir o valor esperado hasta corregirla (fase posterior).

## Resultados (mismos partidos para todas las filas)

| Variante | Acierto | Brier | Log loss | Pendiente calibración |
|---|---|---|---|---|
| Solo modelo, pila logística (fase 0) | 64,8 % | 0,2217 | 0,6344 | 0,93 |
| Margen del modelo, curva normal | 64,5 % | 0,2214 | 0,6334 | 1,06 |
| Margen del modelo, tabla discreta | 64,5 % | 0,2214 | 0,6333 | 1,05 |
| Margen + lesiones, tabla discreta (candidato) | 63,9 % | 0,2201 | 0,6305 | 1,06 |
| Margen + lesiones, curva normal | 63,9 % | 0,2202 | 0,6306 | 1,07 |
| Lesiones con un solo coeficiente (exploratorio) | 64,0 % | 0,2200 | 0,6303 | 1,06 |
| Lesiones sí/no sin probabilidades (exploratorio) | 63,7 % | 0,2203 | 0,6309 | 1,06 |
| Mercado (cierre sin comisión) | 66,4 % | 0,2111 | 0,6097 | 1,06 |

Diferencias por pares (bootstrap por partidos, 10000 remuestreos, negativo = el primero es mejor):

| Comparación | Δ log loss | IC 95 % | Δ Brier | IC 95 % | Δ acierto |
|---|---|---|---|---|---|
| Con lesiones menos sin lesiones (principal) | −0,0028 | [−0,0056; +0,0000] | −0,0013 | [−0,0025; +0,0000] | −0,6 pp |
| Tabla discreta menos curva normal (sin lesiones) | −0,0001 | [−0,0003; +0,0001] | −0,0000 | [−0,0001; +0,0000] | 0,0 pp |
| Candidato menos pila lógica de la fase 0 | −0,0039 | [−0,0075; −0,0003] | −0,0015 | [−0,0031; +0,0000] | −0,9 pp |
| Sin lesiones, tabla discreta menos pila de la fase 0 | −0,0011 | [−0,0033; +0,0010] | −0,0003 | [−0,0012; +0,0006] | −0,3 pp |
| Candidato menos mercado | +0,0208 | [+0,0136; +0,0281] | +0,0091 | [+0,0058; +0,0123] | −2,5 pp |
| Sin lesiones menos mercado | +0,0236 | [+0,0160; +0,0312] | +0,0103 | [+0,0069; +0,0138] | −2,0 pp |
| Pila de la fase 0 menos mercado | +0,0247 | [+0,0169; +0,0329] | +0,0106 | [+0,0071; +0,0142] | −1,6 pp |
| Un solo coeficiente menos sin lesiones (exploratorio) | −0,0030 | [−0,0058; −0,0002] | −0,0014 | [−0,0026; −0,0001] | −0,5 pp |
| Lesiones sí/no menos sin lesiones (exploratorio) | −0,0024 | [−0,0050; +0,0002] | −0,0011 | [−0,0023; +0,0000] | −0,8 pp |
| Sí/no menos probabilidades de jugar (exploratorio) | +0,0004 | [−0,0008; +0,0016] | +0,0001 | [−0,0004; +0,0007] | −0,2 pp |

En los 579 partidos con un ajuste de 1 punto o más (donde hay más efecto): Δ log loss −0,0073 (IC [−0,0171; +0,0024]), error del margen −3,54 puntos² (IC [−8,63; +1,19]).

Solo 2020 a 2025 (1616 partidos, periodo elegido después de ver la tabla por temporada, orientativo): Δ log loss −0,0056 (IC [−0,0089; −0,0025]). En 2018 y 2019 los coeficientes aún venían casi del prior y empeoran el resultado.

## Por temporada (log loss)

| Temporada | Partidos | Mercado | Sin lesiones | Con lesiones | Δ |
|---|---|---|---|---|---|
| 2018 | 258 | 0,615 | 0,629 | 0,638 | +0,0088 |
| 2019 | 259 | 0,619 | 0,639 | 0,642 | +0,0034 |
| 2020 | 261 | 0,589 | 0,619 | 0,616 | −0,0030 |
| 2021 | 271 | 0,622 | 0,645 | 0,639 | −0,0052 |
| 2022 | 269 | 0,609 | 0,637 | 0,633 | −0,0041 |
| 2023 | 272 | 0,627 | 0,651 | 0,648 | −0,0031 |
| 2024 | 272 | 0,587 | 0,610 | 0,598 | −0,0119 |
| 2025 | 271 | 0,609 | 0,637 | 0,631 | −0,0064 |

## Qué pesa cada grupo

Coeficiente = cuántos puntos de margen se pierden por cada punto de impacto esperado (1 significaría que el valor por jugador está bien escalado). Ajuste de toda la muestra por mínimos cuadrados, error típico clásico:

| Grupo | Coeficiente | Error típico | IC 95 % | Frente al spread del mercado |
|---|---|---|---|---|
| QB | 0,70 | 0,19 | [+0,32; +1,07] | 0,11 ± 0,19 |
| RB, WR y TE | 1,03 | 0,38 | [+0,28; +1,79] | 0,67 ± 0,38 |
| Línea ofensiva | 0,44 | 0,42 | [−0,39; +1,26] | 0,17 ± 0,41 |
| Frente defensivo (EDGE, DT, LB) | 0,27 | 0,37 | [−0,46; +1,00] | −0,01 ± 0,36 |
| Secundaria (CB, S) | 0,22 | 0,42 | [−0,61; +1,05] | 0,02 ± 0,41 |

Los grupos con más datos y señal son QB y RB/WR/TE. Línea ofensiva, frente defensivo y secundaria tienen intervalos que incluyen el cero y el uno: con este diseño no se pueden separar. El QB ya entra en el modelo base por su identidad (el titular anunciado), así que su coeficiente mide sobre todo la duda del QB `Questionable`.

Coeficientes walk-forward al empezar cada temporada (los que se usan de verdad, con ridge hacia 0,5):

| Temporada | QB | SKILL | OL | FRONT | SECONDARY |
|---|---|---|---|---|---|
| 2018 | 0,72 | 0,44 | 0,55 | 1,20 | 0,56 |
| 2019 | 0,42 | 0,36 | 0,65 | 0,55 | 0,50 |
| 2020 | 0,36 | 0,47 | 0,51 | 0,47 | 0,31 |
| 2021 | 0,34 | 0,64 | 0,45 | 0,41 | 0,19 |
| 2022 | 0,45 | 0,74 | 0,34 | 0,44 | 0,19 |
| 2023 | 0,42 | 0,75 | 0,36 | 0,35 | 0,43 |
| 2024 | 0,47 | 0,78 | 0,22 | 0,47 | 0,30 |
| 2025 | 0,67 | 0,81 | 0,41 | 0,62 | 0,29 |

## Probabilidad de jugar según el parte

Estimada con partes y snaps anteriores a 2026 semana 1, con reducción jerárquica (etiqueta, entrenamiento, posición). Solo cuentan jugadores con etiqueta o con entrenamiento limitado o sin entrenar:

| Etiqueta | Entrenamiento | Casos | WR | QB | CB | OL |
|---|---|---|---|---|---|---|
| Out | completo | 202 | 0 % | 0 % | 0 % | 0 % |
| Out | limitado | 774 | 0 % | 0 % | 0 % | 0 % |
| Out | no entrenó | 9990 | 0 % | 0 % | 0 % | 0 % |
| Doubtful | completo | 60 | 0 % | 0 % | 0 % | 0 % |
| Doubtful | limitado | 447 | 4 % | 0 % | 0 % | 0 % |
| Doubtful | no entrenó | 1358 | 1 % | 0 % | 2 % | 0 % |
| Questionable | completo | 3083 | 84 % | 71 % | 79 % | 76 % |
| Questionable | limitado | 9741 | 71 % | 44 % | 59 % | 68 % |
| Questionable | no entrenó | 2469 | 48 % | 35 % | 35 % | 40 % |
| Probable | completo | 2124 | 96 % | 81 % | 95 % | 95 % |
| Probable | limitado | 382 | 99 % | 96 % | 94 % | 99 % |
| Probable | no entrenó | 47 | 95 % | 94 % | 95 % | 92 % |

## Tabla discreta de márgenes de la NFL

Se estima con todos los partidos anteriores desde 1999 (spread de cierre como margen esperado), con desviación típica 13,2. Peso de cada margen absoluto frente a una curva normal (1 = igual):

| Margen absoluto | Peso |
|---|---|
| 1 | 0,78 |
| 2 | 0,77 |
| 3 | 2,76 |
| 4 | 0,94 |
| 5 | 0,70 |
| 6 | 1,18 |
| 7 | 1,84 |
| 8 | 0,81 |
| 9 | 0,38 |
| 10 | 1,29 |
| 14 | 1,37 |
| 17 | 1,24 |

Probabilidad de que el favorito local gane, y de que cubra la línea, según la tabla discreta y la curva normal, junto a la frecuencia real con la que cubrieron los favoritos con esa línea (todos los partidos desde 1999):

| Spread local | Gana (tabla) | Gana (normal) | Cubre (tabla) | Cubre (normal) | Cubre, histórico (partidos) |
|---|---|---|---|---|---|
| 1,5 | 54,6 % | 54,5 % | 50,8 % | 50,0 % | 51,0 % (210) |
| 2,5 | 57,7 % | 57,5 % | 51,5 % | 50,0 % | 48,6 % (521) |
| 3,5 | 60,7 % | 60,5 % | 46,4 % | 50,0 % | 49,6 % (677) |
| 4,5 | 63,6 % | 63,4 % | 46,6 % | 50,0 % | 49,4 % (269) |
| 6,5 | 69,1 % | 68,9 % | 47,1 % | 50,0 % | 46,9 % (335) |
| 7,5 | 71,7 % | 71,5 % | 44,6 % | 50,0 % | 47,5 % (280) |
| 9,5 | 76,5 % | 76,4 % | 47,2 % | 50,0 % | 48,7 % (156) |
| 10,5 | 78,7 % | 78,7 % | 46,4 % | 50,0 % | 50,8 % (132) |

## Límites y qué sigue

- El parte de lesiones es el último de la semana (jueves a sábado), no una foto de 24 horas antes. La predicción de los martes no puede usarlo: hay que actualizar el viernes.
- El valor por jugador usa EPA, snaps y producción pública. La línea ofensiva y la defensa no tienen estadística individual y entran por prior y cuota de snaps; es lo más débil del modelo.
- El QB titular ya está en el modelo base (nflverse anuncia el titular). Con un QB `Out` se cuenta dos veces solo en parte; el coeficiente walk-forward lo absorbe.
- Se probaron tres variantes de lesiones y dos conversiones; solo la principal está fijada de antemano. El resto es exploratorio.
- No se ha cambiado producción: `ensemblitz predict`, la web y el baseline de CI siguen igual.
