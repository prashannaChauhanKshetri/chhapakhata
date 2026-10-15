# 0001: One Django API with a React single-page app

**Status:** accepted · 2026-10-15

**Context.** Five users on one shop network, offline-first, three developers, a 25-day deadline.

**Decision.** One Django + DRF application exposes a JSON API; a React + Vite app is built to static files and served by Caddy on the same origin. No separate frontend server (Next.js) and no microservices.

**Consequences.** One deployable backend, one database, simple transactions across orders, stock and billing. The frontend can be rebuilt without touching the server. Server rendering and SEO are not needed for an internal tool.
