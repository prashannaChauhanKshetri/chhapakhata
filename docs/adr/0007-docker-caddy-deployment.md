# 0007: Docker Compose with Caddy on the shop computer

**Status:** accepted · 2026-10-15

**Context.** The shop computer may run Windows or Linux; staff use browsers on the LAN; there is no public domain.

**Decision.** Compose services: PostgreSQL 17, Django/gunicorn, django-q2 worker (nightly backup with an rclone crypt online copy), and Caddy serving the app with HTTPS from its internal CA (plain-HTTP fallback available).

**Consequences.** One install procedure for both OSes and identical environments. On Windows, Docker Desktop must auto-start after sign-in; a small Linux box is more robust. Each device installs Caddy's root certificate once.
