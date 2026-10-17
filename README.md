# ChhapaKhata

Print shop management for **OM Traders and Suppliers**, Nepalgunj: orders priced by square foot, a production board, roll-wise stock, billing with Nepal fiscal-year invoices, customer ledger, reports, and offline-first backups.

> Working name. The product name is still to be decided with the client; it appears in one place in the UI (`frontend/src/app/layout/AppLayout.tsx`) and is otherwise read from Shop settings.

## What it does

| Area | Highlights |
|---|---|
| Orders | Live sq-ft calculator (in / ft / cm), minimum-charge rule, add-ons, discount limits per staff, quotations → confirmed orders |
| Production | One job per item, six stages with role rules, overdue highlighting, roll and sq ft recorded when a job leaves Printing, printable job tickets |
| Stock | Roll-wise media (each roll coded), purchases, usage, wastage, counted adjustments, low-stock alerts, append-only stock ledger |
| Billing | Invoices numbered per fiscal year, never deleted (cancel with reason), "Copy of original" on reprints, BS + AD dates, VAT 13 %, A4 / A5 / 3-inch thermal |
| Payments & ledger | Cash, bank, cheque, eSewa / Khalti / Fonepay, credit (udhar); advances; running customer statement |
| Reports | Daily sales, sales summary, pending dues (aged), collections, material vs sales, operator log, stock; Excel and PDF |
| Safety | Personal logins, 3 roles, activity log, nightly backup with retention, encrypted online copy, full Excel export |

## Stack

Django 5.2 LTS · Django REST Framework · PostgreSQL 17 · WeasyPrint · django-q2 — React 19 · TypeScript · Vite · Mantine 9 · TanStack Query — Docker Compose + Caddy for the shop install. Details and reasons: [docs/architecture.md](docs/architecture.md).

## Quick start (development)

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20.19+, PostgreSQL 17, and Pango (`brew install pango` on macOS) for PDFs.

```bash
make setup        # backend + frontend dependencies, PDF fonts, .env
make db           # create database and migrate
make seed         # demo shop: owner / frontdesk / operator, password Demo@2083
make backend      # API on http://127.0.0.1:8000  (separate terminal)
make frontend     # app on http://127.0.0.1:5173  (separate terminal)
```

Open http://127.0.0.1:5173 and sign in. API reference (development only): http://127.0.0.1:8000/api/docs/.

### On a phone (same Wi-Fi), installable and offline

```bash
make lan-backend    # terminal 1: the API, accepting the computer's Wi-Fi address
make lan-app        # terminal 2: the installable app over HTTPS, prints https://<ip>:4173
make lan-ca         # once per phone: lets the phone download and trust the certificate
```

1. **Once per phone**, run `make lan-ca`, open the printed `http://<ip>:8099/...` address on the phone and install the certificate (the command prints the steps for Android and iPhone).
2. Open the printed `https://<ip>:4173` address and sign in.
3. **Install:** Android/Chrome: account menu → **Install app on this device**. iPhone: Safari → Share → **Add to Home Screen**.

The app then opens from the home screen, full screen. If the Wi-Fi drops or the computer is off, it still opens and shows the data last loaded (saved on the phone for 24 hours, removed on sign-out), with a banner; saving waits until the connection is back. `make lan-frontend` is the same over HTTPS with live reload for development. HTTPS keys are made by `make lan-cert` into `.certs/` (git-ignored); the address is re-detected each time.

This is for development and demos; the shop computer runs the production stack in `deploy/` (see [docs/deployment.md](docs/deployment.md)).

## Checks

```bash
make test         # backend (pytest, 148 tests) and frontend (vitest)
make lint         # ruff + eslint + tsc
make e2e          # Playwright: counter → production → delivery flow (servers running, demo data)
make schema       # after changing the API: regenerate OpenAPI + TypeScript types
```

## Layout

```
backend/   Django project (config/) and apps: core, accounts, customers, catalog,
           orders, production, inventory, billing, reports, system
frontend/  React app: src/app (shell, theme, routes), src/features/*, src/components
deploy/    Docker images, Compose stack, Caddy config, install/backup/restore scripts
docs/      Project report, architecture, guides, ADRs, import templates
```

## Documentation

- [Project report](docs/PROJECT_REPORT.md): scope, decisions, status and the proposal traceability checklist
- [Architecture](docs/architecture.md) · [Domain model](docs/domain-model.md) · [API conventions](docs/api.md)
- [Roles and permissions](docs/rbac.md) · [Pricing rules](docs/pricing.md) · [Billing and tax](docs/billing-and-tax.md) · [Inventory](docs/inventory.md)
- [Design system](docs/design-system.md)
- [Deployment at the shop](docs/deployment.md) · [Backup and restore](docs/backup-restore.md)
- User guide: [English](docs/user-guide/en.md) · [नेपाली (draft)](docs/user-guide/ne.md)
- [Architecture decision records](docs/adr/)
