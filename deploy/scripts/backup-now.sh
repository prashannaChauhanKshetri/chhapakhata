#!/usr/bin/env bash
# Take a backup immediately (also available in the app: Settings → Backups).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T api python manage.py run_backup
