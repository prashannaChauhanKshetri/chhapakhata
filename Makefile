# Common development tasks. Run `make help` for the list.
.PHONY: help setup db seed backend frontend lan-backend lan-frontend test test-backend test-frontend e2e lint schema build

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

# This computer's address on the Wi-Fi (macOS, then Linux), for testing on phones.
LAN_IP := $(shell ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $$1}')

lan-backend: ## Like `backend`, but accepts requests from phones on the same Wi-Fi
	@test -n "$(LAN_IP)" || (echo "Not connected to a network" && exit 1)
	cd backend && \
	  ALLOWED_HOSTS=localhost,127.0.0.1,$(LAN_IP) \
	  CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://$(LAN_IP):5173 \
	  uv run python manage.py runserver 127.0.0.1:8000

lan-frontend: ## Like `frontend`, but open to phones on the same Wi-Fi (prints the address)
	@test -n "$(LAN_IP)" || (echo "Not connected to a network" && exit 1)
	@echo ""
	@echo "  On a phone or another computer on the same Wi-Fi, open:  http://$(LAN_IP):5173"
	@echo ""
	cd frontend && npm run dev -- --host 0.0.0.0

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
