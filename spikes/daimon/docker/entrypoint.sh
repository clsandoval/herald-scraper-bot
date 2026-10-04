#!/bin/sh
# Phase 1: no tenant/MA defaults-seeding step -- that CLI command and its
# provisioning machinery are excluded by D-04 (multi-tenant/CLI stripped).
# Just exec the per-process command supplied by fly.toml [processes] or
# docker-compose (including the release-phase `alembic upgrade head`).
set -e

exec "$@"
