#!/bin/sh
# Container entrypoint. `api` runs migrations then gunicorn; `worker` runs the
# background task cluster (nightly backups). Anything else runs as a command,
# e.g. `docker compose run --rm api python manage.py createsuperuser`.
set -e

wait_for_db() {
  python - <<'PY'
import sys, time
import django
from django.db import connection
django.setup()
for attempt in range(60):
    try:
        connection.ensure_connection()
        sys.exit(0)
    except Exception:
        time.sleep(1)
print("Database did not become ready in 60 seconds", file=sys.stderr)
sys.exit(1)
PY
}

case "$1" in
  api)
    wait_for_db
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput --verbosity 0
    python manage.py setup_schedules
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout 120 \
      --access-logfile - \
      --error-logfile -
    ;;
  worker)
    wait_for_db
    exec python manage.py qcluster
    ;;
  *)
    exec "$@"
    ;;
esac
