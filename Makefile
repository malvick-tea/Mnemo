# Mnemo developer shortcuts.
# Run `make help` to see what's available.

SHELL := /bin/bash
COMPOSE_PROD := docker compose -f docker-compose.yml
COMPOSE_DEV  := docker compose -f docker-compose.yml -f docker-compose.dev.yml

# Pin uv for reproducibility.
UV_VERSION ?= 0.5.13

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ \
	    { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ─── First-time setup ────────────────────────────────────────────────────────
.PHONY: bootstrap
bootstrap: ## Interactive first-run setup (writes .env, starts stack)
	./scripts/bootstrap.sh

# ─── Dev stack ───────────────────────────────────────────────────────────────
.PHONY: dev
dev: ## Start dev stack (hot reload, exposed ports, bot in polling mode)
	$(COMPOSE_DEV) up --build

.PHONY: dev-d
dev-d: ## Same as `dev` but detached
	$(COMPOSE_DEV) up -d --build

.PHONY: logs
logs: ## Tail logs from the dev stack
	$(COMPOSE_DEV) logs -f --tail=200

.PHONY: down
down: ## Stop dev stack (keeps volumes)
	$(COMPOSE_DEV) down

.PHONY: nuke
nuke: ## Stop dev stack AND remove volumes. DESTROYS DATA.
	$(COMPOSE_DEV) down -v

# ─── Prod stack ──────────────────────────────────────────────────────────────
.PHONY: prod-up
prod-up: ## Start production stack
	$(COMPOSE_PROD) up -d

.PHONY: prod-pull
prod-pull: ## Pull latest images
	$(COMPOSE_PROD) pull

.PHONY: prod-logs
prod-logs:
	$(COMPOSE_PROD) logs -f --tail=200

# ─── Build / quality gates ──────────────────────────────────────────────────
.PHONY: lint
lint: ## ruff + mypy on all services
	@for svc in api bot workers; do \
	    echo "== ruff $$svc =="; \
	    (cd services/$$svc && uv run ruff check .); \
	    echo "== mypy $$svc =="; \
	    (cd services/$$svc && uv run mypy --strict src); \
	done

.PHONY: fmt
fmt: ## ruff format
	@for svc in api bot workers; do \
	    (cd services/$$svc && uv run ruff format .); \
	done

.PHONY: test
test: ## Run full test suite (unit + integration)
	@for svc in api bot workers; do \
	    echo "== pytest $$svc =="; \
	    (cd services/$$svc && uv run pytest -q); \
	done

.PHONY: test-unit
test-unit:
	@for svc in api bot workers; do \
	    (cd services/$$svc && uv run pytest -q -m "not integration"); \
	done

.PHONY: test-int
test-int: ## Integration tests against real Postgres/Qdrant/Redis (testcontainers)
	cd services/api && uv run pytest -q -m integration

.PHONY: eval
eval: ## RAG eval suite
	cd services/api && uv run pytest -q tests/eval

# ─── DB / migrations ─────────────────────────────────────────────────────────
.PHONY: migrate
migrate: ## Apply Alembic migrations against the running dev DB
	$(COMPOSE_DEV) exec api uv run alembic upgrade head

.PHONY: migration
migration: ## Make a new migration: `make migration name=add_foo`
	$(COMPOSE_DEV) exec api uv run alembic revision --autogenerate -m "$(name)"

# ─── n8n ─────────────────────────────────────────────────────────────────────
.PHONY: n8n-up
n8n-up: ## Start only n8n + its deps (useful for workflow editing)
	$(COMPOSE_DEV) up -d n8n api postgres qdrant redis minio

.PHONY: n8n-import
n8n-import: ## Re-import all workflows from n8n/workflows/
	./scripts/n8n_import.sh

# ─── Backups ─────────────────────────────────────────────────────────────────
.PHONY: backup
backup: ## Snapshot Postgres + Qdrant + MinIO to ./backups/<UTC>/
	./scripts/backup.sh

.PHONY: restore
restore: ## Restore latest snapshot. Usage: make restore DIR=./backups/2026-05-27T12-00Z
	./scripts/restore.sh $(DIR)

# ─── Demo / screenshots ──────────────────────────────────────────────────────
.PHONY: seed-demo
seed-demo: ## Populate a demo dataset for README screenshots
	$(COMPOSE_DEV) exec api uv run python scripts/seed_demo.py
