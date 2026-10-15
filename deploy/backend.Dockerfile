# ChhapaKhata backend: Django + gunicorn (api) and the django-q2 worker share this image.
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# System libraries: Pango for WeasyPrint PDFs, PostgreSQL 17 client for pg_dump
# (must match the server version), rclone for the encrypted online backup copy.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 shared-mime-info \
        postgresql-client-17 rclone tzdata \
    && apt-get purge -y gnupg && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.25 /uv /usr/local/bin/uv

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --system --uid 1000 --home /app chhapakhata \
    && mkdir -p /data/media /data/static /data/backups /data/logs \
    && chown -R chhapakhata /data /app
USER chhapakhata

ENV MEDIA_ROOT=/data/media STATIC_ROOT=/data/static BACKUP_DIR=/data/backups LOG_DIR=/data/logs

COPY --chown=chhapakhata deploy/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["api"]
