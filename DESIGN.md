# DESIGN.md, ensemblitz

Estado: aprobado por Jesús (papel gris, Archivo condensada, banderas modelo sin mercado frente a consenso de casas con umbral de 5 pp). Implementado en `src/ensemblitz/site/`. Cualquier cambio de dirección visual lo decide él (R-37 de antislop). Las reglas de agentes están en `AGENTS.md` y `.cursor/rules/antislop.mdc`.

## 1. Lectura de diseño

Reading this as: panel de pronósticos NFL para aficionados que consultan los domingos por la noche (hora de Madrid) sobre todo desde el móvil, en un lenguaje de **marcador de estadio y hoja de apuntes de apuestas**, con dial **ENERGY 3 / RHYTHM 3 / MOTION 2**.

- ENERGY 3: titular de jornada a 160 px en condensada negra, marcadores en matriz de puntos, un amarillo de bandera que solo aparece donde hay una discrepancia.
- RHYTHM 3: cabecera asimétrica 7/5, banderas en tarjetas de tamaño distinto (la grande lleva sombra dura, la pequeña no), lista densa por días, notas al pie en dos columnas. No hay dos secciones con la misma composición.
- MOTION 2: casillas de la barra que se encienden una vez, dígitos del marcador que giran una vez, indicador deslizante en la navegación, hover en filas. Nada en bucle.

Pregunta de identidad (core, "Core Principle"): si quitas el nombre, sigue siendo ensemblitz por tres cosas: números en matriz de puntos, barras de 20 casillas con la brecha en amarillo, titulares en condensada extrema.

## 2. Qué se conserva y qué cambia respecto a la web actual

Se conserva: tinta casi negra sobre fondo claro, un único acento, filas tipo tabla con filetes finos, tipografía mono para cifras, tono sobrio en español, hora de Madrid, columnas Hora / Partido / Probabilidad / Marcador / Margen / Mercado / Mejor cuota.

Cambia:
- Fondo crema y serif Fraunces fuera. Crema + serif + un acento cálido es hoy la paleta por defecto de muchos asistentes de IA y no dice "deporte". Pasa a gris papel neutro (#F4F4F2) y grotesca condensada.
- El rojo pasa a amarillo bandera, y solo para marcar brechas, nunca como color de marca general.
- Las etiquetas en versalitas con tracking amplio desaparecen (R-06). Las etiquetas son texto normal de 12 a 13 px.
- Cuadros vacíos con ruta de repo fuera. Textos de plantilla fuera. Códigos de casas fuera (nombres propios).

## 3. Tipografía (todo libre, SIL OFL 1.1, autoalojado en woff2, sin CDN de Google)

| Rol | Fuente | Licencia | Por qué (R-06) |
|---|---|---|---|
| Titulares, equipos, interfaz, texto | **Archivo** (variable, ejes wght 100-900 y wdth 62-125) | OFL 1.1 | Grotesca de herencia deportiva. El eje de anchura da una sola familia con voz condensada para titulares y códigos de equipo (wdth 62, peso 800) y anchura normal para texto (wdth 100). No es de la lista por defecto (Inter, Geist, Space Grotesk). |
| Cifras de tablas (cuotas, %, margen, hora) | **IBM Plex Mono** 400/500/600 | OFL 1.1 | Cifras tabulares para que las columnas alineen. Ya estaba en la web, se mantiene. Solo cifras pequeñas, nunca titulares. |
| Marcador y lectores grandes | **Doto** (variable, matriz de puntos) | OFL 1.1 | Es el tablero de estadio. Una sola voz repetida: marcador típico y 3 cifras de la cabecera. |

Reglas:
- Doto solo a 32 px o más, solo cifras, siempre con equivalente textual (`aria-label` en el marcador). Nunca en párrafos.
- Titulares en minúscula/frase normal, `letter-spacing` 0 a -0.01em. Prohibido versalitas con tracking.
- Escala (px): 12 (mínimo, solo metadatos), 13, 15 (cuerpo), 18 (entradilla), 22, 28, 44, 72 (tarjeta principal), 164 (titular de jornada, `clamp(88px, 12.4vw, 164px)`).
- Nota: cuatro de las referencias usan Geist o Inter. Se toma su contención tipográfica, no su fuente.

## 4. Color (cap R-29: 3 neutros + 1 acento)

Contraste WCAG 2.x comprobado en CI con `scripts/check_site.py` (lee los tokens de `site/static/style.css`, misma fórmula que `contrast-check.py` de antislop-human).

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `--paper` | #F4F4F2 | #0E0F11 | Fondo |
| `--surface` | #FFFFFF | #17181B | Tarjetas y fila en hover |
| `--ink` | #101113 | #F2F2EF | Texto, barras, filetes fuertes |
| `--ink-2` | #50525A | #A6A8AF | Texto secundario |
| `--ink-3` | #666870 | #8E9098 | Metadatos mínimos |
| `--rule` | #D5D5D0 | #2A2B30 | Filetes decorativos |
| `--cell-off` | #C9C9C3 | #2E2F34 | Casillas vacías (decorativas, el valor va en texto) |
| `--flag` | #FFD60A | #FFD60A | Brecha modelo/mercado. Solo relleno, con texto `--on-flag` encima |
| `--on-flag` | #101113 | #101113 | Texto sobre amarillo |

Contrastes medidos:

| Par | Ratio | Resultado |
|---|---|---|
| ink / paper (claro) | 17,15 | AAA |
| ink / surface (claro) | 18,89 | AAA |
| ink-2 / paper (claro) | 7,07 | AAA |
| ink-3 / paper (claro) | 5,05 | AA |
| ink-3 / surface (claro) | 5,56 | AA |
| on-flag / flag | 13,38 | AAA |
| ink / paper (oscuro) | 17,10 | AAA |
| ink / surface (oscuro) | 15,83 | AAA |
| ink-2 / paper (oscuro) | 8,07 | AAA |
| ink-2 / surface (oscuro) | 7,47 | AAA |
| ink-3 / paper (oscuro) | 6,02 | AA |
| ink-3 / surface (oscuro) | 5,57 | AA |
| flag / paper (oscuro) | 13,58 | AAA (marca sin texto) |

Reglas de color:
- El amarillo nunca es texto sobre fondo claro (1,3:1). Siempre es relleno con tinta encima.
- Sin verde/rojo semánticos para el signo de la brecha: el signo (+/−) y el número lo dicen. Así no hay dependencia del color (R-32 y accesibilidad).
- Tema: claro por defecto, `prefers-color-scheme` respetado y botón manual. Motivo del oscuro (R-21): los partidos caen entre las 19:00 y las 03:00 en Madrid y mucha gente consulta de noche.
- Prohibido: degradados, orbes de luz, glow, vidrio, segundo acento.

## 5. Rejilla, espaciado y forma

- Contenedor 1240 px, gutter 24 px (16 px en móvil). Cabecera y banderas en 12 columnas, partición 7/5.
- Espaciado: 4, 8, 12, 16, 24, 32, 48, 72, 112. El ritmo cambia a propósito: 72 entre bloques grandes, 48 antes de cada día, 16 dentro de la fila.
- Radios: 2 px en controles y chips, 6 px en tarjetas. Ninguna píldora. Los cuadros de las barras son cuadrados (0).
- Sombra: solo una, dura y sin difuminar (6 px desplazada, color tinta), en la tarjeta de la bandera principal. Motivo (R-12): es el único foco de la pantalla.
- Filetes: 1 px sólido de tinta para cabeceras de día, 1 px punteado para separar filas. El punteado repite el motivo de matriz de puntos y es el único "patrón" de fondo, sin rejillas decorativas (R-07).
- Breakpoints: 1100 (la fila pasa a tarjeta), 900 (cabecera y banderas a una columna), 640 (móvil). Dianas táctiles de 44 px mínimo (chips, botón de tema, navegación).

## 6. Componentes

**Fila de partido** (desktop, 8 columnas): hora Madrid + fecha | visitante *en* local en condensada 34 px y nombres completos debajo | probabilidad | marcador en Doto | margen del favorito | mercado | brecha | mejor cuota con nombre de casa. Una línea de contexto opcional (descanso, techo cerrado, cambio de QB) solo si el dato la justifica; si no hay, no hay línea. En móvil: hora, partido y marcador arriba; barra a ancho completo; rejilla 2x2 de cifras con etiqueta.

**Barra de probabilidad**: 20 casillas de 5 % (40 en la tarjeta grande). Casillas oscuras = ensemble para el favorito. Línea vertical con remate = mercado (consenso sin margen de las casas). Rombo vacío = modelo sin mirar el mercado. Banda amarilla entre línea y rombo = brecha, solo si |brecha| ≥ 5 pp. La barra lleva `role="img"` con las tres cifras en el `aria-label`. Las casillas se encienden una vez al cargar.

**Marcador**: dos cifras en Doto (visitante, local) con el código de equipo debajo. Los dígitos giran 6 pasos y se fijan al entrar en pantalla, una sola vez. Nota al pie: es el resultado más frecuente de las simulaciones compatibles con ganador y margen, ninguno pasa del 1 %.

**Tabla de cuotas** (página de partido, ordenable con teclado): una fila por casa con nombre propio, cuota decimal con coma, probabilidad sin margen (Shin) y brecha con nuestro número. Orden por cuota para el lado favorito; la mejor, resaltada con filete y no con color. Casa con sufijo de país solo cuando hay duplicado visible. Nunca códigos internos (`betfair_ex_eu`).

**Tira de noticias**: una línea a ancho completo bajo la cabecera. Con noticias: fecha y hora Madrid, jugador, equipo, estado, fuente enlazada con el nombre de la persona o medio, efecto en puntos de margen. Sin noticias: "Sin ajustes por lesiones esta jornada: los pronósticos no incorporan bajas de último momento." y enlace al método. Nunca rutas de archivos ni mensajes de desarrollador.

**Bandera (brecha)**: chip amarillo con icono de bandera y la cifra ("−11 pp"). Es el único uso del amarillo en contenido. La tarjeta de la bandera principal explica en una frase con datos qué lee el modelo y qué lee el mercado, y avisa de que el pronóstico final se apoya sobre todo en el mercado.

**Filtros**: chips rectangulares (Todos, Solo banderas, un chip por día) con recuento. Estado activo en tinta invertida. Funcionan sin recargar.

**Iconos**: conjunto propio de 16 px, trazo 1,5 px, extremos cuadrados, una sola rejilla, tomando de Neat Icons la regla de "una rejilla para todos". Solo los que tienen significado: bandera, techo cerrado, reloj de descanso. Sin chispas, estrellas ni rayos (R-04). Sin emojis.

**Navegación**: logotipo (5 casillas, una amarilla y más alta, que es la bandera) + condensada; enlaces con indicador de 3 px que se desliza al hover y vuelve a la página actual.

## 7. Movimiento (dial 2)

Todo respeta `prefers-reduced-motion` (se apaga).
- Casillas de la barra: `scaleY` y opacidad, 350 ms, escalonado 14 ms por casilla, una vez.
- Dígitos del marcador: 6 cambios aleatorios cada ~45 ms y se fijan, una vez, al 60 % visible.
- Indicador de navegación: 280 ms, `cubic-bezier(.3,.7,.2,1)`.
- Chips y fila: 150 ms de color y fondo, 1 px de desplazamiento al pulsar.
- Cuenta atrás al próximo partido: texto que se calcula al cargar, no parpadea.
- Prohibido: bucles, pulsos, parallax, aparición con retardo del contenido, contadores que suben desde 0.

## 8. Contenido y copy (antislop-copywriting, R-02, R-17)

- Sin raya larga (em dash) en ningún texto. Usar coma, punto, dos puntos o paréntesis.
- Sin "Con honestidad:" ni otras muletillas. Lo que sea una limitación va como dato (por ejemplo, el ajuste por bajas aún no está validado con partidos pasados), en el método, no como preámbulo.
- Una frase de contexto por partido solo si hay un dato que la sostenga. Nada de "parten como favoritos; sin factores fuera de lo normal".
- Unidades españolas: hora de Madrid con "(hora de Madrid)", cifras con coma decimal, espacio duro antes de %. Clima en °C y km/h cuando haya dato real. El clima solo se muestra si `context.weather_known` es 1. Los 58 °F y 7 mph que el pipeline rellenaba por defecto no se muestran (R-17: sin dato real, sin cifra).
- Destacar discrepancias con la métrica correcta: el ensemble final pesa el mercado al 83 %, así que su diferencia con el mercado nunca pasa de 3 pp. La brecha informativa es la del modelo sin mercado (`ensemble_model_only`) frente al consenso.
- Pie: horas de Madrid, no UTC.

## 9. Qué no hacer (resumen de antislop aplicado a este proyecto)

- No degradados ni orbes de luz (referencias evilbuttons e illos los usan: no se copian).
- No fondos con rejilla ni puntos de cuadrícula decorativos (R-07). El único punteado son los filetes de fila.
- No Geist/Inter/Space Grotesk por defecto, no JetBrains/Geist Mono (R-06).
- No bento, no tres columnas idénticas, no "cómo funciona en 3 pasos" (el método es una página de lectura).
- No píldoras ni cápsulas con punto y brillo; no insignia sobre el titular.
- No Lucide ni clones; no flechas en cada botón (R-08).
- No barra de logos ni testimonios inventados; no cifras sin fuente (R-17). Las cifras salen de `predictions/` y `reports/odds/`.
- No acento en más de un sitio: el amarillo marca brechas y el icono del logotipo, nada más.
- No lenguaje de "IA" en la interfaz.

## 10. Qué aporta cada referencia (y qué se descarta)

| Referencia | Se toma | Se descarta |
|---|---|---|
| illos.dev | Hero con ilustración que se dibuja con datos (gráfica hecha de caracteres), un solo acento (turquesa) sobre fondo cálido, chips de estilo con icono | Banner superior, degradado de CTA |
| neaticons.com | Todo el catálogo en una sola rejilla y trazo; hero que es el propio producto | Fondo de iconos como decoración |
| autorouter.com | Lo real en el hero (campo de entrada vivo), muchísimo aire, microinteracciones suaves | Estética de app de Mac |
| ogimagecn.com | Titular denso con tracking negativo, bloque de instalación con pestañas, jerarquía de botones sólido/contorno | Geist, "Copy prompt for your agent" |
| mdxcn.dev | Gráficas dibujadas con texto, títulos entre corchetes, marcos punteados, tabla y línea de tiempo como texto, escritura frente a resultado | Cuadrícula con cruces de fondo, modo oscuro por defecto |
| amicro.dev | Microinteracción con propósito en cada botón, pestañas con indicador que se desliza | Fondo negro total, patrocinadores |
| easyui.site | Tarjetas con cifra grande y tendencia, focos mínimos y curvas de spring en los controles | Radios muy redondos |
| evilbuttons.com | Una sola palabra con voz propia (pixel en rojo) en el titular, componentes que se pueden probar en vivo | Fondo degradado naranja, perspectiva 3D |
| bencho.dev | Chips de filtro con recuento, densidad de tarjetas bien medida, motivo de puntos discreto | Hero centrado con CTA doble |

Rasgos compartidos: producto real a la vista, titulares apretados, neutros con un solo acento, mono para datos, bordes finos y radios pequeños, microinteracción en lo que se toca y nada que se mueva solo.

## 11. Entrega

Antes de dar nada por hecho: `python scripts/check_site.py` (contraste, raya larga, rutas del repo en la salida), 390 px sin desbordes, foco visible de 2 px en tinta con desfase de 3 px, `lang="es"`, `aria-label` en barras y marcadores, Delivery Gate de antislop pasado por quien implemente. Los archivos de fuente van en `site/static/fonts/` con sus licencias.

## 12. Convenciones de datos en pantalla

- Margen: siempre el favorito y los puntos que da, con signo menos y coma decimal ("HOU −12,5"). Nunca un margen del local sin nombre.
- Banderas: |`ensemble_model_only` menos consenso de casas sin margen (Shin)| ≥ 5 pp. El umbral vive en `FLAG_PP` (`site/build.py`) y en `BIG_EDGE` (`odds/report.py`).
- Horas: siempre Europe/Madrid, también en cabecera y pie ("Datos del 17 nov 2026, 23:15 (Madrid)").
- Casas de apuestas: nombre propio (`site/names.py`, `book_name`). Una clave desconocida se muestra en capitalización de título, nunca cruda.
- Estados vacíos: texto humano, sin rutas del repositorio. Si no hay noticias, bloque corto y enlace al método.
