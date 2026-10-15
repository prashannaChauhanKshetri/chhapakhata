#!/usr/bin/env bash
# Install a new version: backup first, then rebuild and restart.
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/backup-now.sh
git -C .. pull --ff-only
docker compose up -d --build
docker compose ps
