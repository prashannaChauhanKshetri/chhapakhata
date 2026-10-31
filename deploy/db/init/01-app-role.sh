#!/bin/sh
# First start of a new database volume: create the app's own non-superuser role
# and make it the owner (see ../app-role.sql). Upgrades use scripts/app-role.sh.
set -e
if [ -z "${APP_DB_PASSWORD:-}" ]; then
  echo "APP_DB_PASSWORD is not set in deploy/.env" >&2
  exit 1
fi
psql -X -q --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_role=chhapakhata_app -v app_password="$APP_DB_PASSWORD" \
  -f /opt/chhapakhata/app-role.sql
