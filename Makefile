PIPELINE ?= demo_matricula
ENV ?= dev

.PHONY: lint fmt fmt-check type test ci env config run

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

fmt-check:
	uv run ruff format --check .

type:
	uv run pyright

# Tests con coverage (texto + xml, alineado con GitHub Actions)
test:
	uv run pytest -q --cov=shared --cov=pipelines --cov-report=term-missing --cov-report=xml:coverage.xml

ci: lint fmt-check type test
	@echo "CI checks OK ✅"

# Crea .env desde .env.example si no existe (NO sobreescribe)
env:
	@test -f .env || (cp .env.example .env && echo "Creado .env desde .env.example (edita .env con secretos reales)")

# Valida que config/<ENV>.yml + .env cargan correctamente
config:
	uv run python -c "from shared.config import load_settings; s=load_settings('$(ENV)'); print('OK settings:', s.app.env, s.postgres.host)"

run: env
	PYTHONPATH=. uv run python -m shared.cli run --pipeline $(PIPELINE) --env $(ENV)
