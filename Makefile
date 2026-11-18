.PHONY: install update backtest baseline check predict grade odds test lint all
install:
	uv venv --python 3.13 .venv || true
	uv pip install -e ".[dev]"
update:
	ensemblitz update
backtest:
	ensemblitz backtest
baseline:
	ensemblitz baseline --full
check:
	ruff check . && ruff format --check . && pytest -q && ensemblitz site && python scripts/check_site.py && python scripts/validate_outputs.py --site site/_build && python scripts/check_baseline.py
predict:
	ensemblitz predict
grade:
	ensemblitz grade
odds:
	ensemblitz odds
test:
	pytest -q
lint:
	ruff check . && ruff format --check .
all: update backtest predict grade
