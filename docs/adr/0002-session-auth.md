# 0002: Session cookies with CSRF, not JWT

**Status:** accepted · 2026-10-15

**Context.** The app and API share one origin on the shop LAN.

**Decision.** Django sessions (HttpOnly cookie, SameSite=Lax, 12-hour sliding expiry) with CSRF tokens on unsafe requests. Login lockout via django-axes (5 failures, 15 minutes).

**Consequences.** No tokens in browser storage, no refresh logic, server-side logout. Cross-origin API clients are not supported (none are planned; "remote owner access" is a separate add-on).
