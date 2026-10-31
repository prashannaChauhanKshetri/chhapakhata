# 0008: Several businesses on one site, kept apart by row-level security

**Status:** accepted · 2026-10-31

**Context.** One server should host more than one print shop: the online demo needs a shop with six years of history next to an empty one, and later several shops may share a cloud server. Each shop must never see or change another's orders, customers or money. The code has about 190 ORM queries and 28 querysets built at import time, so filtering by hand in every query would be easy to get wrong once.

**Decision.**

- Every shop table has a `business` column, filled automatically from the current scope (`apps/tenancy/context.py`).
- PostgreSQL row-level security, forced even for the table owner, shows and accepts only rows whose `business_id` matches the session setting `app.business_id`. `BusinessMiddleware` sets it per request from the signed-in user; commands use `--business`.
- The app connects as `chhapakhata_app`, a role that is not a superuser, because superusers skip row-level security.
- Users stay in one site-wide table (sign-in must find them before the business is known), and usernames are unique site-wide. Code that reads users filters by business itself.
- Each business keeps its own settings, its own invoice and receipt numbering (gap-free per fiscal year), and its own unique names.
- Migrations, backups and platform commands (`create_business`, `list_businesses`) set `app.rls_bypass` to see every business. Any database client could set that flag, so the policies guard against application mistakes, not against someone who already has database access.

**Consequences.**

- A missed filter shows an empty list instead of another shop's data, and a write with the wrong `business_id` fails.
- New shop tables must inherit `BusinessOwned` and add `enable_rls` in their migration. `test_every_business_table_has_a_forced_policy` fails if one is missed.
- Tests and CI must connect as the app role, or isolation goes untested (`test_app_role_is_subject_to_row_level_security`).
- A new thread or background task starts with no business and sees nothing until it calls `use_business`.
- Backups contain every business. A restore replaces all of them together.
