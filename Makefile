.PHONY: install lock-check update backtest baseline check predict grade odds test lint all
# Python version comes from .python-version (3.12, the same as CI); dependencies from uv.lock.
install:
	uv lock --check
	uv sync --frozen --extra dev
lock-check:
	uv lock --check
update:
	uv run --frozen ensemblitz update
backtest:
	uv run --frozen ensemblitz backtest
baseline:
	uv run --frozen ensemblitz baseline --full
check: lock-check
	uv run --frozen ruff check . && uv run --frozen ruff format --check . && uv run --frozen pytest -q && uv run --frozen ensemblitz site && uv run --frozen python scripts/check_site.py && uv run --frozen python scripts/validate_outputs.py --site site/_build && uv run --frozen python scripts/check_baseline.py
predict:
	uv run --frozen ensemblitz predict
grade:
	uv run --frozen ensemblitz grade
odds:
	uv run --frozen ensemblitz odds
test:
	uv run --frozen pytest -q
lint:
	uv run --frozen ruff check . && uv run --frozen ruff format --check .
all: update backtest predict grade
