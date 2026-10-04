FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY herald/ ./herald/
RUN uv sync --frozen --no-dev --no-editable
RUN useradd --uid 1000 --create-home herald && mkdir /data && chown herald:herald /data
COPY docker/entrypoint.py ./docker/entrypoint.py
ENV PATH="/app/.venv/bin:$PATH" HERALD_DB="/data/herald.db" HERALD_REPORT_DB="/data/herald-reports.db"
ENTRYPOINT ["python", "/app/docker/entrypoint.py"]
# Pick a mode explicitly. The default only prints help; it never connects online.
CMD ["python", "-m", "herald", "--help"]
