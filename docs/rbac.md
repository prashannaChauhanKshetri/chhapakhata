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

## Orders on the customer's account

- A **confirmed order counts** on the customer's statement and in dues from its order date, billed or not (ledger line "Order"). Editing it posts the difference; cancelling it takes it off.
- **Making a bill moves** the order onto the bill ("Work moved to a bill"), so it is never counted twice; cancelling the bill puts it back on the account.
- Imported work-log orders work the same way, with the line "Work (imported)".

## Production tracking

- **Settings → Shop → Track production** (owner): off hides the production board, job stages, job tickets, Urgent and Deliver. Orders are then confirmed, billed (Issue invoice / Make a bill) and paid. Nothing is deleted; switching it on brings everything back.

## Staff and salary

- **Staff** are workers on the payroll, separate from logins (helpers need no account). When someone leaves, switch off "Still working here" and set the last working day; the record and its slips are kept. Only a worker with no salary paid and no advance given (e.g. added by mistake) can be deleted.
- **Attendance** is marked by hand: every working day counts as present unless marked absent; Saturday (the weekly holiday) counts as off unless marked worked. Any past day can be corrected, from the daily register or a worker's month calendar.
- **Pay** for a BS month: one day's pay = monthly salary ÷ days in that month. Each absent day takes off one day's pay; each Saturday worked adds one day's pay, or the worker's own **Saturday pay** when the owner has set an amount. Advances given in the month are taken off; advances larger than the pay move to the next month.
- **Starting with existing workers:** each can have a balance up to the end of a BS month (unpaid salary owed to them, or an old advance they owe). Pay is counted from the next month, where that balance is added or taken off once; days up to the balance month cannot be marked. The balance cannot change once a month after it is paid.
- **A month still running** shows the salary earned to date (the days up to today), growing each day. It can be paid from its last day on, or earlier for a worker who has left; money given before that is an advance.
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
