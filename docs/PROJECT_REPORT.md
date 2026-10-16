# ChhapaKhata: Project Report

**Client:** OM Traders and Suppliers, Nepalgunj-12, Banke (Mr. Anil Pokhrel)
**Team:** Prashanna Chauhan Kshetri (lead), Nitisha Gyawali, Tenjeeb K.C.
**Proposal date:** 15 October 2026 · **Demo due:** 25 October 2026 · **Completion due:** 9 November 2026
**Report status:** MVP feature-complete in development (15 October 2026). Not yet installed at the shop.

---

## 1. Purpose

OM Traders prices custom flex, vinyl and signage work by hand, tracks jobs in notebooks, runs out of rolls unexpectedly and loses track of dues. The proposal commits to one offline system for orders, production, roll-wise stock, billing, payments, the customer ledger, reports and backups (proposal §3). This report records what was built, why, and what remains before handover.

**MVP scope = every item in proposal §3.1–3.8.** Optional add-ons in §4.2 (SMS, offcuts, supplier ledger, glow-sign calculator, IRD/CBMS e-billing, remote access) are out of scope.

## 2. Decisions

| Topic | Decision | Why |
|---|---|---|
| Backend | Django 5.2 LTS + DRF + PostgreSQL 17 | Long-term support to 2028; strong admin, migrations and transactions for money |
| Frontend | React 19 + Vite + TypeScript + Mantine 9 | Static build served by Caddy: no Node server in the shop. Same library family as InvenTree |
| Auth | Django session cookie + CSRF, same origin | Simpler and safer than tokens in browser storage on a LAN |
| Roles | Fixed three-role matrix in code | Mirrors proposal §3.1 exactly; tested endpoint by endpoint |
| Pricing | Server-side engine only; UI calls a preview endpoint | One calculator, so the screen always matches the bill |
| Money | `Decimal`, rounded half-up to 2 places at each step | Matches Nepali billing practice; no float errors |
| Ledgers | Append-only stock movements and customer ledger | Every change is traceable; corrections are new entries |
| Jobs | One job per order item | Each item has its own material, roll and stage |
| PDFs | WeasyPrint with bundled fonts | Identical documents offline; supports A4, A5 and 80 mm |
| Deployment | Docker Compose + Caddy (LAN HTTPS) | Same stack on Windows (Docker Desktop) or Linux |
| UI palette | Client's slate palette (#F8FAFC, #E2E8F0, #94A3B8, #334155, #0F172A) | Requested by the client; colour beyond slate only for status |
| Language | English UI routed through i18n | Nepali screens can be added without touching components |

Full reasoning is in [adr/](adr/).

## 3. What was built

### Backend (`backend/apps/`)

| App | Responsibility |
|---|---|
| `core` | Shop settings (singleton, history-tracked), gap-free document numbering per fiscal year, BS dates and fiscal years, money helpers (lakh grouping, amount in words), activity log, permission engine, PDF rendering |
| `accounts` | Staff accounts with roles, discount limits, login lockout, 5-active-user cap, last-owner protection |
| `customers` | Customers with trigram search, opening balances, statements (JSON/PDF/Excel), owner adjustments |
| `catalog` | Media types and add-ons with rate history; the pricing engine |
| `orders` | Quotations, confirmation, editing with rate snapshots, cancellation, deliver-and-settle |
| `production` | Jobs, stage rules per role, material requirement when leaving Printing, board, job tickets |
| `inventory` | Stock items, rolls, suppliers, purchases, usage, wastage, adjustments, roll finishing |
| `billing` | Invoices (immutable, cancel with reason, print count), payments (all modes, void), ledger, statements, ageing |
| `reports` | Seven reports in one format-neutral structure rendered to JSON, Excel and PDF; role-aware dashboard |
| `system` | Backups (pg_dump + media, checksum, retention, rclone online copy), data export, import and seed commands |

### Frontend (`frontend/src/features/`)

Dashboard (per role) · Orders list, calculator form, detail, deliver dialog · Production board (desktop columns, phone tabs), job drawer, material dialog · Customers list, detail with statement · Invoices list and detail with printing · Payments list and receive dialog · Inventory list, item detail with rolls and history, purchases · Reports index and generic report page · Settings: shop, rate card, users, backups and export, activity log.

### Deployment (`deploy/`)

Backend image (WeasyPrint libraries, PostgreSQL 17 client, rclone, non-root user), web image (built React app + Caddy), Compose stack (db, api, worker, web) with health checks and restart policies, HTTPS and plain-HTTP Caddy configs, install / backup / restore / update scripts for Linux and Windows.

## 4. Proposal traceability (§3)

| Proposal item | Where in the app | API | Tests |
|---|---|---|---|
| **3.1** Roles and permissions matrix | Navigation, route guards, buttons hidden per role | `HasPerm` on every view | `core/tests/test_rbac_matrix.py` (every endpoint × role) |
| 3.1 Personal login, actions recorded | Sign-in page; Settings → Activity log | `auth/*`, `activity/` | `accounts/tests/test_auth.py` |
| 3.1 Up to 5 user accounts | Settings → Users | `users/` | `test_active_user_cap` |
| **3.2** Customer search / quick add | Customer picker with "+" in the order form | `customers/?search=` | API tests |
| 3.2 Size in in / ft / cm, auto sq ft | Order form item rows | `orders/price-preview/` | `catalog/tests/test_pricing.py` |
| 3.2 Media types with rates | Settings → Rate card | `media-types/` | pricing + RBAC tests |
| 3.2 Minimum billing rule | Badge "Min. 5 sq ft" on the item | engine | `test_minimum_sqft_applies_per_piece` |
| 3.2 Add-ons (design, eyelets, framing, lamination, pockets, urgent) | Add-ons field per item | `addons/` | `test_addon_bases` (all five bases) |
| 3.2 Several items per order | "Add another item" | nested items | order service tests |
| 3.2 Discount with staff limit | Summary panel | limit check | `test_front_desk_discount_limit` |
| 3.2 Price formula | Summary panel | engine | `test_order_totals_with_percent_discount_and_vat` |
| **3.3** Automatic Job ID (JOB-1001) | Order detail, board cards | sequences | `test_job_numbers_start_at_1001` |
| 3.3 Printable job ticket | Board drawer, order menu | `jobs/{id}/ticket/`, `orders/{id}/job-tickets-pdf/` | smoke tests |
| 3.3 Design file reference | Item "Design file" field, ticket | item field | — |
| 3.3 Production board on computer and phone | Production page (columns / tabs) | `jobs/board/` | E2E flow |
| 3.3 Due today / overdue highlight | Card borders, header badges, dashboard | board flags | — |
| 3.3 Six stages, who updates | Card buttons and move menu | `jobs/{id}/move/` | `production/tests/test_services.py` |
| **3.4** Roll-wise tracking | Inventory → item → Rolls | `rolls/` | `inventory/tests/test_services.py` |
| 3.4 Automatic deduction | Material dialog when leaving Printing | `move` with material | `test_leaving_printing_requires_material`, E2E |
| 3.4 Wastage | Material dialog, item "Record → Wastage" | `stock-items/{id}/wastage/` | wastage tests |
| 3.4 Other items (ink, eyelets, frames, standees) | Inventory | `stock-items/` | `test_non_roll_items_opening_and_usage` |
| 3.4 Purchase entry | Purchases → Record purchase | `purchases/` | `test_purchase_creates_rolls_and_movements` |
| 3.4 Owner-only adjustment with reason | Item "Adjust after count" | `stock-items/{id}/adjust/` | `test_adjust_to_counted_quantity`, RBAC |
| 3.4 Low-stock alert | Dashboard, inventory filter | `stock-items/?low=true` | — |
| **3.5** Quotation PDF | Order menu → Print quotation | `orders/{id}/quotation-pdf/` | smoke |
| 3.5 Advance and partial payments | Receive payment, deliver dialog | `payments/` | `test_advance_then_settle_then_void` |
| 3.5 A4 / A5 / 3-inch thermal | Invoice → Print | `invoices/{id}/print/?size=` | report/PDF tests |
| 3.5 VAT, fiscal-year numbers, BS + AD dates | Invoice documents | `issue_invoice` | `test_invoice_numbers_restart_each_fiscal_year`, `test_fiscal_year_boundaries` |
| 3.5 Customer ledger and statement | Customer → Statement (print / Excel) | `customers/{id}/statement/` | `test_opening_balance_and_statement` |
| 3.5 Cancel with reason, never delete | Invoice → Cancel (owner) | `invoices/{id}/cancel/` | `test_cancel_keeps_number_and_reverses_ledger` |
| 3.5 Payment modes (cash, bank, cheque, QR wallets, credit) | Payment and deliver dialogs | `payments/` | `test_payment_mode_details_required` |
| **3.6** Seven reports, Excel / PDF | Reports | `reports/{slug}/?export=` | `reports/tests/test_reports.py` (all × 3 formats) |
| 3.6 Report access by role | Reports index | per-report permission | RBAC matrix |
| **3.7** Runs in the shop, no internet needed | Caddy on the LAN, self-hosted fonts | — | offline banner; manual drill |
| 3.7 Daily backup | Settings → Backups | django-q2 schedule | `test_run_backup_creates_dump`, restore drill |
| 3.7 Online copy | rclone crypt remote | `sync_offsite` | manual |
| 3.7 Data export | Settings → Backups → Export | `system/export/` | `test_export_all_data` |
| **3.8** Installation for 5 users | `deploy/scripts/install.*` | — | compose validated |
| 3.8 Initial data entry | `import_rate_card`, `import_customers`, `import_opening_stock` | — | `system/tests/test_imports.py` |
| 3.8 Printer setup, training, user guide | [deployment.md](deployment.md), [user-guide](user-guide/) | — | at the shop |

## 5. Quality status (16 October 2026)

| Check | Result |
|---|---|
| Backend tests (pytest) | 172 passed |
| Backend coverage | 88 % overall; services 80–100 % |
| Frontend unit tests (Vitest) | 18 passed |
| End-to-end (Playwright) | Counter → production with material → delivery, invoice and payment; drag-and-drop on the board (allowed and refused moves): passing |
| Lint / format / types | ruff, ESLint, Prettier, `tsc --strict`: clean |
| OpenAPI schema | Generated and validated; TypeScript types generated from it |
| Backup and restore | Real `pg_dump`, checksum verified, restore drill row counts identical |
| Docker images | Compose file validated; **images not yet built** on a machine with Docker running |

## 5a. Changes after the client's feedback (16 October 2026)

| Request | What was built | Where |
|---|---|---|
| Import and export the shop's Excel work log | Upload with a dry-run preview (columns found, new customers and items, errors and notes per row), then import. Rows become delivered orders (one per date and customer), ledger charges without invoices, and receipts. Re-uploading skips rows already imported. Export writes orders in the same column layout; a blank template is downloadable. | `apps/system/work_log.py`, Settings → Import & export |
| Rate = the customer's previous rate, or a new rate | Per-line rate field defaulting to the customer's last rate, one-click rate card, custom rates checked against the discount limit, `rate_source` and `card_rate` stored on each line | `apps/orders/selectors.py`, `services.py`, `ItemRow.tsx` |
| Items sold per piece (seen in the sheet: photos, name plates, 3D letters) | Rate-card items priced per sq ft **or per piece**; size optional, no minimum | `catalog/pricing.py`, Settings → Rate card |
| Draggable production board | Drag-and-drop with @dnd-kit (mouse, touch, keyboard). Drops follow the same role rules as the buttons; the material dialog opens when needed; the card moves at once and is confirmed by the server. | `production/BoardPage.tsx`, `useJobMover.ts` |
| Better ledger: opening, closing and more | Statement with BS period presets, opening/closing rows, Dr/Cr balances, type totals, aging, linked references. New Ledger page with customer balances (opening, billed, received, closing, last payment) and a day book. PDF and Excel. | `billing/selectors.py`, `LedgerPage.tsx` |

## 6. Risks and open items

| Risk / item | Impact | Action |
|---|---|---|
| IRD billing rules for software invoices | If the shop is VAT-registered above the IRD threshold, billing software may need IRD approval and CBMS sync (paid add-on) | Ask the client's auditor before system invoices replace the printed invoice book |
| Rate card, media list, opening stock and dues | Needed for go-live | Client fills the CSV/Excel templates in `docs/templates/` |
| Invoice layout, stamp and signature | Client will supply | Upload in Settings → Shop; adjust `backend/templates/documents/invoice.html` if a custom layout is needed |
| Shop computer OS and power | Windows Docker Desktop starts only after sign-in | Enable auto start and auto sign-in, or use a small Linux PC; recommend a UPS |
| Pricing conventions | Sq ft rounding, VAT-inclusive rates, front-desk discount limit | Confirm at the shop visit; all are settings |
| Thermal printer model | 80 mm receipts print through the browser | Test with the actual printer driver during installation |
| Nepali user guide | Drafted, needs native review | Team review before training |
| Work-log column meanings | The sheet's "Payment S" column was read as the amount paid and "Payment M" as the payment mode | Confirm with the shop before importing the full sheet; the preview lists how every column was read |
| Imported history and invoices | Imported work has no invoices, so VAT and invoiced-sales reports exclude it | Expected; confirm the client agrees |

## 7. Next steps to handover

1. **Shop visit (16 Oct):** confirm pricing conventions, VAT status, hardware; collect rate card and opening data.
2. **Demo (by 25 Oct):** run with seeded demo data, then with the client's real rate card.
3. **Install (5–9 Nov):** build images on the shop computer, import data, configure printers and the online backup remote, install the root certificate on staff devices, train staff, run the restore drill.
4. **Before go-live:** change all demo passwords; create real accounts; confirm the first nightly backup and its online copy.
