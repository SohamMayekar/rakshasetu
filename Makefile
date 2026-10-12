# RakshaSetu: one-command setup. `make help` lists the targets.
SHELL := /bin/bash
API := services/api
WEB := apps/web

COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: help env up down nuke ps logs smoke psql demo-sheet sheet-eval screens e2e contracts seed demo-reset surge verify tamper provider-check keys copy-check dev-api dev-web test test-api test-web lint

help: ## List the targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  make %-12s %s\n", $$1, $$2}'

env: ## Create .env from .env.example if it doesn't exist
	@test -f .env || (cp .env.example .env && echo "created .env (no keys: fixture mode)")

up: env ## Build and start the whole stack (db, api, worker, ticker, web)
	$(COMPOSE) up -d --build --wait

down: ## Stop the stack (data volume kept)
	$(COMPOSE) down

seed: ## Wipe the demo database and load the BR, OD and HP scenario packs (DEMO_MODE only)
	$(COMPOSE) exec -T api python -m app.seed

demo-reset: ## Reset the demo to a scene's starting point (make demo-reset SCENE=stale; scenes in data/scenarios/BR/demo.yaml)
	$(COMPOSE) exec -T api python -m app.modules.demo.scenes --scene $(or $(SCENE),son)
surge: ## Synthetic partner-report surge through the public listener (make surge RATE=50 DURATION=60); watch /surge
	$(COMPOSE) exec -T api python -m app.surge --rate $(or $(RATE),50) --duration $(or $(DURATION),60)
verify: ## Verify the audit hash chain of the demo database
	$(COMPOSE) exec -T api python -m app.verify_chain

tamper: ## Q&A demo: quietly edit event #SEQ as the superuser (make tamper SEQ=812), then make verify
	$(COMPOSE) exec -T -e SEQ=$(or $(SEQ),5) db psql -U postgres -d rakshasetu -f - < scripts/tamper.sql

provider-check: ## One tiny synthetic call to each provider whose key is in .env (OK / BLOCKED / FAILED)
	$(COMPOSE) exec -T -e PROVIDER_MODE=live api python -m app.providers.check

keys: ## Print a fresh PHONE_ENC_KEY (Fernet) for .env
	@services/api/.venv/bin/python -c "from cryptography.fernet import Fernet; print('PHONE_ENC_KEY=' + Fernet.generate_key().decode())"

nuke: ## Stop the stack AND delete the database volume (fresh start)
	$(COMPOSE) down -v

psql: ## Open psql on the demo database as the superuser (the tamper demo)
	$(COMPOSE) exec db psql -U postgres -d rakshasetu

ps: ## Show service health
	$(COMPOSE) ps

logs: ## Follow logs (make logs s=worker)
	$(COMPOSE) logs -f $(s)

smoke: ## Check both Caddy listeners from outside (rule R18)
	./scripts/smoke_listeners.sh

demo-sheet: ## Regenerate the 300-row demo volunteer sheet and its ground truth (deterministic)
	services/api/.venv/bin/python scripts/gen_demo_sheet.py

sheet-eval: ## Import the demo sheet into the TEST database and print time, outcome agreement, merge precision/recall
	$(COMPOSE) exec -T api pytest -s -q -p no:cacheprovider tests/scenarios/test_demo_sheet.py

screens: ## Screenshots at 1366×768 and phone: make screens OUT=docs/screens/m32 PAGES="/ui#design-system /r#reporter"
	cd apps/web && node e2e/shoot.mjs ../../$(OUT) $(PAGES)

e2e: ## The golden path (PRD §16.1) through the real screens on the running stack; resets the demo; screenshots in docs/screens/golden
	cd apps/web && node e2e/golden.mjs
contracts: ## Regenerate packages/contracts/openapi.json from the code
	services/api/.venv/bin/python scripts/export_openapi.py

dev-api: ## Run the API natively on :8000 (needs services/api/.venv)
	cd $(API) && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-web: ## Run the web app natively on :3000
	cd $(WEB) && npm run dev

test: up copy-check test-api ## Rebuild if needed, then run every test (the web app is type-checked by its own build)

copy-check: ## Never-say words must not appear on any screen (CLAUDE.md §7)
	python3 scripts/check_copy.py

test-api: ## Lint + API tests, inside the api container, against the rakshasetu_test database
	$(COMPOSE) exec -T api sh -c "ruff check app tests && pytest"

test-web: ## Web typecheck
	cd $(WEB) && npx tsc --noEmit

lint: ## Ruff on the API
	cd $(API) && .venv/bin/ruff check app tests
