# syntax=docker/dockerfile:1.7
#
# Multi-stage build:
#   base  → minimal runtime (libpq, curl)
#   deps  → adds build-essential, installs Python packages
#   dev   → adds source code + uvicorn --reload (used by docker-compose)
#   prod  → minimal runtime + non-root user + gunicorn (used by Render/Railway)
#
# Build for prod explicitly:
#   docker build --target=prod -t jobtracker-api:prod .

# ---------- base (shared by dev + prod runtime) ----------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Runtime-only system deps (asyncpg + bcrypt need libpq + libssl at runtime).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*


# ---------- deps (everything needed to install Python packages) ----------
FROM base AS deps

# Build deps for any C-extension wheels that have to compile from source.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt


# ---------- dev (used by docker-compose for hot-reload) ----------
FROM deps AS dev

# Source is bind-mounted in dev — copy is just so the image is runnable
# standalone too.
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


# ---------- prod (final, hardened) ----------
FROM base AS prod

# Bring in the installed packages from `deps` but NOT build-essential.
# This is what makes the prod image small (~200MB vs ~600MB).
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Non-root user
RUN useradd --create-home --shell /bin/bash --uid 1000 app

COPY --chown=app:app . /app
RUN chmod +x /app/entrypoint.sh

USER app
WORKDIR /app

EXPOSE 8000

# entrypoint runs alembic upgrade then exec's whatever command follows.
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command: gunicorn with uvicorn workers.
# WEB_CONCURRENCY (env) overrides worker count — Render/Railway set it
# automatically based on plan size; we default to 4 if unset.
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w ${WEB_CONCURRENCY:-4} --bind 0.0.0.0:8000 --access-logfile - --error-logfile - --timeout 120"]
