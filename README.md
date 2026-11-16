# ChhapaKhata

**Print shop management system** for flex, banner, signage and photo printing houses in Nepal: orders priced by the square foot, a production board, roll-wise stock, IRD-style billing in Bikram Sambat, customer accounts (khata), reports and safe backups. Everything is in one web app that works on the shop computer, on phones, and online.

*Chhapa* (छापा) means print and *khata* (खाता) the account book.

One installation can serve **several print shops**. Each shop has its own staff, prices, customers, bill numbering and data, and no shop can see another's. The first shop to use it is OM Traders and Suppliers, Nepalgunj.

---

## Features

### Counter: orders and quotations
- **Live price calculator:** width × height in inches, feet or cm, with the shop's minimum sq ft for small jobs. Items can also be priced per piece (photo prints, name plates, 3D letters).
- **The customer's own rates:** a returning customer's last rate is filled in, the rate card is one click away, and any custom rate is checked against the staff member's discount limit.
- **Add-ons:** design, eyelets, framing, lamination, pockets, urgent. Charged fixed, per piece, per sq ft, per running ft or as a percentage.
- **Quotations:** a printable A4 quotation that becomes a confirmed order in one click.
- **Customers from the order screen:** search by name, phone or PAN; add a new customer without leaving the order. Adding items to the rate card works the same way (owner).

### Production board
- **One job per item:** six stages from design to delivery, with drag and drop, undo, and red/amber edges for overdue and due-today work.
- **Role rules:** front desk approves designs, operators print, and nothing is printed before the proof is approved.
- **Material on every print:** the roll and sq ft used, plus wastage, recorded as a job leaves Printing. A5 job tickets, and progress bars on every order.

### Billing and payments
- **IRD-style bills:**
  - invoice and receipt numbers run gap-free and restart each fiscal year (1 Shrawan);
  - bills show BS and AD dates, the buyer's PAN, VAT 13 % and the amount in words;
  - reprints are marked "Copy of original".
- **Never deleted:** wrong bills are cancelled and payments voided, always with a reason. A payment entered wrongly is fixed with **Correct payment**, which keeps both receipts on record.
- **Every way of paying:** cash, bank transfer, cheque, eSewa / Khalti / Fonepay / QR, advances, and credit (udhar).
- **Printing:** 3-inch thermal, A5 or A4, with the shop's logo, stamp and signature.

### Customer accounts (khata) and ledger
- **Statements:** a running statement per customer for any BS period (opening balance, bills, payments, closing balance), printable or in Excel.
- **Opening balances from last year:** dated at the fiscal year's close and correctable with a reason and a full change history.
- **Customer balances:** every customer in one sortable, paged list with totals, plus a day book and dues ageing.
- **Append-only ledger:** corrections are new entries, never edits.

### Stock and purchases
- **Roll-wise media:** each roll coded, with sq ft left.
- **Movements:** purchases with supplier bills, usage, wastage, counted adjustments and low-stock alerts, all in an append-only stock ledger.

### Reports and insights
- **Reports:** daily sales, sales summary, pending dues (aged), collections by mode, material consumption vs sales, operator production log and stock. Each prints to PDF or exports to Excel for any BS month or fiscal year.
- **Insights:** sales trends, best customers and items, and a dues follow-up list.

### Bringing in a shop's old records
- **Imports:** the old Excel **work log** (past orders), **customers with opening balances**, **payments received**, the **rate card** and **opening stock**.
- **Any sheet layout:**
  - **File types:** .xlsx, .xls, .xlsm, .xlsb, .ods, CSV or a web page saved as Excel; one sheet or one per month.
  - **Columns:** the shop's own names in any order, including Nepali headings.
  - **Dates and numbers:** BS or AD dates; amounts like "Rs. 1,20,000/-".
- **Check first:** the file is checked before anything is saved, with notes and problem rows listed and columns that can be corrected by hand.
- **Never counted twice:** a payment in both the work log and the payments sheet is recorded once, even when the day's payments are split differently. So is anything dated inside an opening balance, a re-uploaded sheet, or a row edited after import.
- **Export:** orders in the same work-log layout, or every table as one Excel file.

### Safety and administration
- **Accounts:** personal logins with three roles (owner, front desk, operator), lock-out after wrong passwords, and an activity log of who did what.
- **Backups:** nightly backup with daily, weekly and monthly retention, an encrypted online copy, and tested restore scripts.
- **Several shops on one server:** PostgreSQL row-level security keeps each shop's data apart.
- **Starting fresh:** the owner can delete all data, after typing Confirm and with a backup taken first.

### Works where the shop works
- **Phones:** an installable app (Add to Home Screen) that keeps showing the last data when the connection drops.
- **Easy to use:** BS dates throughout, keyboard shortcuts, adjustable text size, and skeleton loaders instead of spinners.
- **Two ways to run it:** on the shop computer (Docker, HTTPS on the local network) or online on a cloud server with automatic HTTPS.

---

## Stack

Django 5.2 LTS · Django REST Framework · PostgreSQL 17 (row-level security) · WeasyPrint · django-q2. React 19 · TypeScript · Vite · Mantine 9 · TanStack Query. Docker Compose + Caddy. Details and reasons: [docs/architecture.md](docs/architecture.md).

## Quick start (development)

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 20.19+, PostgreSQL 17, and Pango (`brew install pango` on macOS) for PDFs.

```bash
make setup        # backend + frontend dependencies, PDF fonts, .env
make db           # database + its non-superuser app role, then migrations
make seed         # demo shop: owner / frontdesk / operator, password Demo@2083
make backend      # API on http://127.0.0.1:8000  (separate terminal)
make frontend     # app on http://127.0.0.1:5173  (separate terminal)
```

Open http://127.0.0.1:5173 and sign in. API reference (development only): http://127.0.0.1:8000/api/docs/.

### Several shops on one installation

```bash
cd backend
uv run python manage.py create_business --name "Sharma Prints" --owner-username ram
uv run python manage.py list_businesses
```

Each shop's owner then adds staff in Settings → Users. With more than one shop, data commands take `--business <slug>`.

### Six years of demo history (separate database)

```bash
make history          # builds `chhapakhata_history`: a shop from 1 Shrawan 2077 BS to today (about 30–40 min)
make backend-history  # run the API on that database instead of the demo one
```

Sign in as **newowner** (owner), **sunita** / **anjali** (front desk) or **kamal** / **suresh** (operators); password **Shop@2077**. The shop grows from one owner and a small rate card through staff changes, yearly rate rises, new products, VAT registration, festival seasons, the Covid lockdowns and the 2079 election rush. Every event goes through the normal business rules in date order, so bill numbers, the ledger and stock reconcile exactly. All names, phones and PANs are invented.

### On a phone (same Wi-Fi), installable and offline

```bash
make lan-backend    # terminal 1: the API, accepting the computer's Wi-Fi address
make lan-app        # terminal 2: the installable app over HTTPS, prints https://<ip>:4173
make lan-ca         # once per phone: lets the phone download and trust the certificate
```

Open the printed address on the phone, sign in, and install it (Android: account menu → **Install app on this device**; iPhone: Share → **Add to Home Screen**).

## Running it for a shop

- **On the shop computer:** Docker Compose with HTTPS on the local network. See [docs/deployment.md](docs/deployment.md).
- **Online:** a small cloud server (tested on AWS EC2 t3.small) with a domain and automatic Let's Encrypt HTTPS. See [docs/deploy-aws.md](docs/deploy-aws.md).
- **Updates:** `deploy/scripts/update.sh` backs up, pulls, rebuilds and migrates.
- **Backups and restores:** [docs/backup-restore.md](docs/backup-restore.md).

## Checks

```bash
make test         # backend (pytest, 360 tests) and frontend (vitest)
make lint         # ruff + eslint + tsc
make e2e          # Playwright browser tests (servers running, demo data)
make schema       # after changing the API: regenerate OpenAPI + TypeScript types
make user-guide   # rebuild the PDF user guide from docs/user-guide/en.md
```

Tests run as the app's non-superuser database role, so the row-level security that separates shops is exercised on every run.

## Layout

```
backend/   Django project (config/) and apps: tenancy, core, accounts, customers,
           catalog, orders, production, inventory, billing, reports, system
frontend/  React app: src/app (shell, theme, routes), src/features/*, src/components
deploy/    Docker images, Compose stack, Caddy config, database role, install/update/backup/restore scripts
docs/      User guide (+ PDF), architecture, guides, ADRs, import templates, feature prompts
scripts/   Development helpers (local HTTPS certificates, database role, user-guide PDF)
```

## Documentation

- **User guide:** [English](docs/user-guide/en.md) · [PDF](docs/user-guide/ChhapaKhata-User-Guide.pdf) · [नेपाली (draft)](docs/user-guide/ne.md)
- **Project:** [Project report](docs/PROJECT_REPORT.md) (scope, decisions, status)
- **Technical:** [Architecture](docs/architecture.md) · [Domain model](docs/domain-model.md) · [API conventions](docs/api.md)
- **Business rules:** [Roles, permissions and shops](docs/rbac.md) · [Pricing rules](docs/pricing.md) · [Billing and tax](docs/billing-and-tax.md) · [Inventory](docs/inventory.md)
- **Design:** [Design system](docs/design-system.md) · [UX golden rules](docs/ux-golden-rules.md)
- **Running it:** [Deployment at the shop](docs/deployment.md) · [Online on AWS EC2](docs/deploy-aws.md) · [Backup and restore](docs/backup-restore.md)
- **Decisions:** [Architecture decision records](docs/adr/), including [several shops with row-level security](docs/adr/0008-multi-business-rls.md)
