#!/usr/bin/env bash
# Make sure the app connects as its own non-superuser database role.
# Row-level security keeps each business's data apart, and PostgreSQL skips it
# for superusers. Safe to run again; update.sh and restore.sh call it.
# Usage: ./scripts/app-role.sh   (from the deploy/ folder)
set -euo pipefail
cd "$(dirname "$0")/.."

if ! grep -q '^APP_DB_PASSWORD=..' .env; then
  password=$(openssl rand -base64 32 | tr -d '\n/+=' | cut -c1-32)
  if grep -q '^APP_DB_PASSWORD=' .env; then
    sed -i.bak "s|^APP_DB_PASSWORD=.*|APP_DB_PASSWORD=${password}|" .env && rm -f .env.bak
  else
    printf '\n# Password of the app'"'"'s own database role (see scripts/app-role.sh)\nAPP_DB_PASSWORD=%s\n' "$password" >> .env
  fi
  echo "Added APP_DB_PASSWORD to deploy/.env."
fi
password=$(grep '^APP_DB_PASSWORD=' .env | tail -1 | cut -d= -f2-)

docker compose up -d db
# Over TCP: a brand-new volume's first-start setup listens on the socket only.
for _ in $(seq 1 90); do
  docker compose exec -T db pg_isready -h 127.0.0.1 -U chhapakhata -d chhapakhata >/dev/null 2>&1 && break
  sleep 1
done
docker compose exec -T db psql -X -q -U chhapakhata -d chhapakhata \
  -v app_role=chhapakhata_app -v app_password="$password" -f - < db/app-role.sql
echo "The app's database role is ready."
