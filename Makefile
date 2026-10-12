# RakshaSetu: one-command setup. `make help` lists the targets.
SHELL := /bin/bash
API := services/api
WEB := apps/web

COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: help env up down ps logs dev-api dev-web test test-api test-web lint

help: ## List the targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  make %-12s %s\n", $$1, $$2}'

env: ## Create .env from .env.example if it doesn't exist
	@test -f .env || (cp .env.example .env && echo "created .env (no keys: fixture mode)")

up: env ## Build and start the whole stack (db, api, worker, ticker, web)
	$(COMPOSE) up -d --build --wait

down: ## Stop the stack (data volume kept)
	$(COMPOSE) down

ps: ## Show service health
	$(COMPOSE) ps

logs: ## Follow logs (make logs s=worker)
	$(COMPOSE) logs -f $(s)

dev-api: ## Run the API natively on :8000 (needs services/api/.venv)
	cd $(API) && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-web: ## Run the web app natively on :3000
	cd $(WEB) && npm run dev

test: test-api test-web ## Run every test

test-api: ## API tests, run inside the api container against the db service
	$(COMPOSE) exec -T api pytest

test-web: ## Web typecheck
	cd $(WEB) && npx tsc --noEmit

lint: ## Ruff on the API
	cd $(API) && .venv/bin/ruff check app tests
