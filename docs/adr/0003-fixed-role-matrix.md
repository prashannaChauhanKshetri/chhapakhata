# 0003: A fixed role matrix in code

**Status:** accepted · 2026-10-15

**Context.** The proposal defines exactly three roles and their rights (§3.1).

**Decision.** Permissions are string constants; `ROLE_PERMISSIONS` maps each role to its set; every view declares `required_perms` per action and is denied by default. The matrix is tested endpoint by endpoint.

**Consequences.** Easy to read and audit; impossible to misconfigure from the admin. Custom roles would need a code change (InvenTree-style group rulesets can be added later if the shop grows).
