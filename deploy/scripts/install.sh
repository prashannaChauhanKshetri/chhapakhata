#!/usr/bin/env bash
# First-time installation on a Linux (or macOS) shop computer with Docker.
# Usage: ./scripts/install.sh            (run from the deploy/ folder)
set -euo pipefail
cd "$(dirname "$0")/.."

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker with the compose plugin is required. See docs/deployment.md." >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  secret=$(openssl rand -base64 48 | tr -d '\n/+=' | cut -c1-60)
  dbpass=$(openssl rand -base64 32 | tr -d '\n/+=' | cut -c1-32)
  apppass=$(openssl rand -base64 32 | tr -d '\n/+=' | cut -c1-32)
  sed -i.bak -e "s|^SECRET_KEY=.*|SECRET_KEY=${secret}|" -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${dbpass}|" \
    -e "s|^APP_DB_PASSWORD=.*|APP_DB_PASSWORD=${apppass}|" .env
  rm -f .env.bak
  echo "Created deploy/.env with fresh secrets. Review SITE_ADDRESS and ALLOWED_HOSTS now, then re-run."
  exit 0
fi

mkdir -p backups rclone
./scripts/app-role.sh
docker compose up -d --build

echo "Waiting for the app to start..."
for _ in $(seq 1 90); do
  if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/', timeout=3)" >/dev/null 2>&1; then
    echo "ChhapaKhata is running."
    break
  fi
  sleep 2
done

echo
echo "Next: create the owner account:"
echo "  docker compose run --rm api python manage.py create_owner --username <name> --first-name <First>"
echo "More shops on this server, each with its own data:"
echo "  docker compose exec api python manage.py create_business --name \"<Shop name>\" --owner-username <name>"
echo "Then open https://$(grep '^SITE_ADDRESS=' .env | cut -d= -f2 | cut -d, -f1) on any device in the shop."
