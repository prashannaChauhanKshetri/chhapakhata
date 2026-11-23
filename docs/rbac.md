# Roles and permissions

Source of truth: `backend/apps/core/permissions.py` (`ROLE_PERMISSIONS`). The frontend mirror (`frontend/src/lib/permissions.ts`) only hides controls; the server enforces every rule. `core/tests/test_rbac_matrix.py` checks each endpoint for each role.

| Capability (proposal §3.1) | Owner | Front desk | Operator |
|---|---|---|---|
| Set rates, media types, minimum charges | ✓ | | |
| Create customers and orders | ✓ | ✓ | |
| Quotations, invoices, receipts | ✓ | ✓ | |
| Receive payments and advances | ✓ | ✓ | |
| View production board and job tickets | ✓ | ✓ | ✓ |
| Update job status | ✓ | ✓ (stages 1, 2, 6) | ✓ (stages 3, 4, 5) |
| Enter material used and wastage | ✓ | | ✓ |
| Stock purchase and adjustment | ✓ | | |
| Customer ledger and dues | ✓ | view only | |
| Reports | all | daily sales | own production log |
| Manage users and passwords | ✓ | | |
| Cancel invoices, void payments, adjust balances | ✓ | | |
| Activity log, backups, data export, shop settings | ✓ | | |
| Staff list, attendance, advances and salary | ✓ | | |

## Production stage rules

- Front desk moves jobs into **Design / Proof sent**, **Ready for print** and **Delivered**.
- Operators move jobs into **Printing**, **Finishing** and **Ready for collection**, and only after front desk has marked the job **Ready for print** (nothing is printed before the proof is approved).
- **Delivered** is allowed only from **Ready for collection** (owner excepted). Only the owner reopens a delivered job.
- Leaving **Printing** requires the roll and sq ft used for media linked to stock; the owner may skip this.

## Staff and salary

- **Staff** are workers on the payroll, separate from logins (helpers need no account). Never deleted: set the last working day when someone leaves.
- **Attendance** is marked by hand: every working day counts as present unless marked absent; Saturday (the weekly holiday) counts as off unless marked worked.
- **Pay** for a BS month: one day's pay = monthly salary ÷ days in that month. Each absent day takes off one day's pay; each Saturday worked adds one. Advances given in the month are taken off; advances larger than the pay move to the next month.
- **Paying** a month records the figures for the salary slip and locks that month's attendance and advances. The owner can undo a payment with a reason (logged).

## Other rules

- **Discount limit:** front desk default 10 % of the sub-total (Shop settings), overridable per user. The owner has no limit.
- **Accounts:** at most 5 active accounts (`MAX_ACTIVE_USERS`); at least one active owner must remain. Accounts are deactivated, never deleted.
- **Sign-in:** 5 wrong passwords lock that username on that device for 15 minutes. Sessions last 12 hours from the last activity.

## Businesses

One site can host several businesses (print shops). Each account belongs to one business and sees only that business's data. PostgreSQL row-level security enforces this, so a missed filter in the code cannot show another shop's records (see [ADR 0008](adr/0008-multi-business-rls.md)).

- **Usernames** are unique across the whole site. The username decides which business an account opens.
- **Per business:** settings, rate card, customers, orders, stock, invoice and receipt numbering, reports, exports, the activity log and the active-account limit (`MAX_ACTIVE_USERS` applies to each business).
- **New business:** the site operator runs `manage.py create_business --name "<Shop>" --owner-username <name>` on the server. The owner then adds staff in Settings → Users.
- **Pausing a business:** set it inactive in the Django admin (Businesses). Its staff can no longer sign in.
- **Starting again:** the owner can delete their own business's data (Settings → Backups & export → Delete all data, typing "Confirm"). Logins, settings and the activity log stay, a backup is taken first, and no other business is touched.
- **Backups** cover the whole site. Any owner's "Backup now" backs up every business, and a restore replaces every business together.
