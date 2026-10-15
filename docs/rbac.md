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

## Production stage rules

- Front desk moves jobs into **Design / Proof sent**, **Ready for print** and **Delivered**.
- Operators move jobs into **Printing**, **Finishing** and **Ready for collection**, and only after front desk has marked the job **Ready for print** (nothing is printed before the proof is approved).
- **Delivered** is allowed only from **Ready for collection** (owner excepted). Only the owner reopens a delivered job.
- Leaving **Printing** requires the roll and sq ft used for media linked to stock; the owner may skip this.

## Other rules

- **Discount limit:** front desk default 10 % of the sub-total (Shop settings), overridable per user. The owner has no limit.
- **Accounts:** at most 5 active accounts (`MAX_ACTIVE_USERS`); at least one active owner must remain. Accounts are deactivated, never deleted.
- **Sign-in:** 5 wrong passwords lock that username on that device for 15 minutes. Sessions last 12 hours from the last activity.
