# Daimon scaffold — unfinished experiment

This is the previous Postgres/Anthropic workspace, preserved intact for research. The Discord adapter answers mentions with `pong`; the scheduler is inert and the Alembic baseline creates no Herald domain tables. It does not power scheduled reports or `/heralds`.

Its `pyproject.toml`, `uv.lock`, Dockerfile, compose file and Fly test-app template are independent of the root product. If working specifically on this experiment, run `uv sync --frozen` here. The original secret-free environment template is available as `.env.example`; its Anthropic key requirement belongs only to this scaffold. Running its adapters is a separate live operation.

Offline tests (after installing this workspace):

```sh
uv run pytest tests packages/adapters/discord/tests -q
```

No scaffold deploy, migration or paid agent call was performed during the October handoff. The root application's dependencies no longer install this unfinished stack by default.
