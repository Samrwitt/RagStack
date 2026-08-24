.PHONY: up down logs ps migrate test test-unit test-integration lint fmt typecheck api-shell health

COMPOSE ?= docker compose

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api worker migrate

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) run --rm migrate

health:
	curl -sS http://localhost:8000/health | python -m json.tool
	curl -sS http://localhost:8000/api/v1/health | python -m json.tool

test-unit:
	cd backend && python -m pytest tests/unit -q

test-integration:
	cd backend && python -m pytest tests/integration -q

test: test-unit

lint:
	cd backend && ruff check app tests && ruff format --check app tests

fmt:
	cd backend && ruff check --fix app tests && ruff format app tests

typecheck:
	cd backend && mypy app

api-shell:
	$(COMPOSE) exec api bash
