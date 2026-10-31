#!/usr/bin/env bash
# Development: create the non-superuser app role and give it a local database.
# Usage: scripts/db-app-role.sh [database]   (default: chhapakhata)
set -euo pipefail
db="${1:-chhapakhata}"
psql -X -q -d "$db" -v app_role=chhapakhata_app -f "$(dirname "$0")/../deploy/db/app-role.sql"
echo "Database '$db' is owned by chhapakhata_app (row-level security applies to the app)."
