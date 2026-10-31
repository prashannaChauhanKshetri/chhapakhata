#!/usr/bin/env bash
# Restore a backup set. THIS REPLACES ALL CURRENT DATA.
# Usage: ./scripts/restore.sh backups/sets/chhapakhata-db-YYYYMMDD-HHMMSS.dump
#        (the matching chhapakhata-media-*.tar.gz, if present, is restored too)
set -euo pipefail
cd "$(dirname "$0")/.."

dump="${1:-}"
if [ -z "$dump" ] || [ ! -f "$dump" ]; then
  echo "Give the path to a chhapakhata-db-*.dump file." >&2
  exit 1
fi
media="${dump/chhapakhata-db-/chhapakhata-media-}"
media="${media%.dump}.tar.gz"
checksum="${dump%.dump}.sha256"

if [ -f "$checksum" ]; then
  (cd "$(dirname "$dump")" && sha256sum -c "$(basename "$checksum")") || { echo "Checksum mismatch: the backup file is damaged." >&2; exit 1; }
fi

echo "This will REPLACE all current data with: $dump"
read -r -p "Type RESTORE to continue: " answer
[ "$answer" = "RESTORE" ] || { echo "Cancelled."; exit 1; }

docker compose stop api worker web
docker compose exec -T db sh -c 'dropdb -U chhapakhata --if-exists chhapakhata && createdb -U chhapakhata chhapakhata'
docker compose exec -T db pg_restore -U chhapakhata -d chhapakhata --no-owner --exit-on-error < "$dump"
# Restored as the superuser: hand the tables back to the app's role.
./scripts/app-role.sh

if [ -f "$media" ]; then
  docker compose run --rm -T -v "$(cd "$(dirname "$media")" && pwd)":/restore:ro --entrypoint sh api \
    -c "rm -rf /data/media/* && tar -xzf /restore/$(basename "$media") -C /data"
fi

docker compose up -d
echo "Restore finished. Sign in and check recent orders and balances."
