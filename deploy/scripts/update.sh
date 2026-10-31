#!/usr/bin/env bash
# Install a new version: backup first, then rebuild and restart.
# Everything runs from main(), which bash reads in full before starting, so
# `git pull` replacing this file mid-run cannot break it.
set -euo pipefail
cd "$(dirname "$0")/.."

main() {
  ./scripts/backup-now.sh
  git -C .. pull --ff-only
  ./scripts/app-role.sh
  docker compose up -d --build
  docker compose ps
}

main "$@"
