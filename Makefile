# Common development tasks. Run `make help` for the list.
.PHONY: help setup db seed backend frontend test test-backend test-frontend e2e lint schema build

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

setup: ## Install backend and frontend dependencies, copy fonts
	cd backend && uv sync
	cd frontend && npm install && npm run fonts:pdf
	@test -f .env || (cp .env.example .env && echo "Created .env; edit DATABASE_URL if needed")

db: ## Create the local database and apply migrations
	createdb chhapakhata 2>/dev/null || true
	cd backend && uv run python manage.py migrate

seed: ## Fill an empty database with demo data (owner / frontdesk / operator, password Demo@2083)
	cd backend && uv run python manage.py seed_demo

backend: ## Run the Django API on :8000
	cd backend && uv run python manage.py runserver 127.0.0.1:8000

frontend: ## Run the web app on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

test: test-backend test-frontend ## Run all unit and API tests

test-backend:
	cd backend && uv run pytest --cov

test-frontend:
	cd frontend && npm test

e2e: ## Browser tests (needs `make backend`, `make frontend` and demo data)
	cd frontend && npx playwright test

lint: ## Lint and type-check everything
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npm run typecheck

schema: ## Regenerate the OpenAPI schema and frontend API types after API changes
	cd backend && uv run python manage.py spectacular --file schema.yml --validate
	cd frontend && npm run api:types

build: ## Production frontend build
	cd frontend && npm run build
