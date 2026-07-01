#!/bin/sh
# Phase 1: no `daimon defaults apply` -- that CLI command and its tenant/MA
# provisioning machinery are excluded by D-04 (multi-tenant/CLI stripped).
# Just exec the per-process command supplied by fly.toml [processes] or
# docker-compose (including the release-phase `alembic upgrade head`).
set -e

exec "$@"
