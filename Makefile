.PHONY: install update backtest predict grade odds test lint all
install:
	uv venv --python 3.13 .venv || true
	uv pip install -e ".[dev]"
update:
	ensemblitz update
backtest:
	ensemblitz backtest
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
