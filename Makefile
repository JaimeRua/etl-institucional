PIPELINE ?= demo_matricula
ENV ?= dev

.PHONY: lint fmt type test run

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

type:
	uv run pyright

test:
	uv run pytest -q --cov=shared --cov=pipelines --cov-report=term-missing

run:
	PYTHONPATH=. uv run python -m shared.cli run --pipeline $(PIPELINE) --env $(ENV)

