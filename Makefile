PIPELINE ?= demo_matricula
ENV ?= dev

.PHONY: lint fmt fmt-check type test ci run

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

fmt-check:
	uv run ruff format --check .

type:
	uv run pyright

test:
	uv run pytest -q --cov=shared --cov=pipelines --cov-report=term-missing

ci: lint fmt-check type test
	@echo "CI checks OK ✅"

run:
	PYTHONPATH=. uv run python -m shared.cli run --pipeline $(PIPELINE) --env $(ENV)
