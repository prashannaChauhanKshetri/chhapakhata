# Common development tasks. Run `make help` for the list.
.PHONY: help setup db seed backend frontend lan-backend lan-frontend lan-app lan-cert lan-cert-check lan-ca test test-backend test-frontend e2e lint schema build

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
	  CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://localhost:5173,https://$(LAN_IP):5173,https://localhost:4173,https://$(LAN_IP):4173 \
	  uv run python manage.py runserver 127.0.0.1:8000

lan-cert: ## HTTPS certificate for this computer's Wi-Fi address (made automatically when needed)
	@test -n "$(LAN_IP)" || (echo "Not connected to a network" && exit 1)
	@scripts/dev-cert.sh $(LAN_IP)

lan-cert-check:
	@test -n "$(LAN_IP)" || (echo "Not connected to a network" && exit 1)
	@test -f .certs/dev.pem -a "$$(cat .certs/dev.ip 2>/dev/null)" = "$(LAN_IP)" || scripts/dev-cert.sh $(LAN_IP)

lan-frontend: lan-cert-check ## Like `frontend`, over HTTPS for phones on the same Wi-Fi (prints the address)
	@echo ""
	@echo "  On a phone on the same Wi-Fi, open:  https://$(LAN_IP):5173"
	@echo "  (first time on a phone: run 'make lan-ca' and install the certificate)"
	@echo ""
	cd frontend && VITE_HTTPS=1 npm run dev -- --host 0.0.0.0

lan-app: lan-cert-check ## The installable app (production build) for phones: Add to Home Screen, works offline
	cd frontend && npm run build
	@echo ""
	@echo "  On a phone on the same Wi-Fi, open:  https://$(LAN_IP):4173"
	@echo "  Then choose 'Install app' (Android) or Share > Add to Home Screen (iPhone)."
	@echo ""
	cd frontend && VITE_HTTPS=1 npx vite preview --host 0.0.0.0 --port 4173

lan-ca: lan-cert-check ## Let a phone download the certificate authority to trust the HTTPS address (once per phone)
	@mkdir -p .certs/share && cp .certs/chhapakhata-dev-ca.crt .certs/share/
	@echo ""
	@echo "  On the phone, open:  http://$(LAN_IP):8099/chhapakhata-dev-ca.crt"
	@echo "  Android: Settings > Security > Encryption & credentials > Install a certificate > CA certificate"
	@echo "  iPhone:  Settings > Profile Downloaded > Install, then"
	@echo "           Settings > General > About > Certificate Trust Settings > turn on ChhapaKhata Dev CA"
	@echo "  Press Ctrl+C here when done."
	@echo ""
	@cd .certs/share && python3 -m http.server 8099 --bind 0.0.0.0

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
