# Instrucciones para agentes

- Idioma de la web, informes y commits de contenido: español de España. Horas en Europe/Madrid, cifras con coma decimal, °C y km/h.
- Diseño: seguir `DESIGN.md`. No cambiar tokens, fuentes ni la dirección visual sin que Jesús lo apruebe.
- Antislop: reglas en `.cursor/rules/antislop.mdc` y copia MIT en `third_party/antislop/` (conservar `LICENSE`). Sin raya larga (em dash) en texto escrito ni en la salida de la web.
- Antes de dar la web por buena: `ruff check .`, `ruff format --check .`, `pytest -q`, `ensemblitz site` y `python scripts/check_site.py`.
- Nunca mostrar en la web rutas del repositorio, claves internas de casas de apuestas, ni cifras imputadas como si fueran datos reales.
- No se toca `main` directamente: ramas y pull requests.
