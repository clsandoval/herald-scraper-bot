# ---------------------------------------------------------------------------
# Stage 1: builder — install build deps + compile wheels
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY packages/ ./packages/

RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2: runtime — slim image, no build tools
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Non-root user
RUN useradd --uid 1000 --create-home daimon

# uv binary needed for `uv run alembic` (release_command runs through the
# same entrypoint/image).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy venv from builder (includes all installed packages via UV_LINK_MODE=copy)
COPY --from=builder --chown=daimon:daimon /app/.venv ./.venv
COPY --from=builder --chown=daimon:daimon /app/pyproject.toml ./pyproject.toml
COPY --from=builder --chown=daimon:daimon /app/packages/ ./packages/

# App config — no `defaults/` dir: Phase 1 excludes tenant/MA provisioning
# machinery entirely (D-04); there is nothing for it to seed.
COPY --chown=daimon:daimon alembic.ini ./

# Entrypoint script (just `exec`'s the process command — no `defaults apply`)
COPY --chown=daimon:daimon docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER daimon

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# No CMD — docker-compose services or fly.toml [processes] supply the command.
