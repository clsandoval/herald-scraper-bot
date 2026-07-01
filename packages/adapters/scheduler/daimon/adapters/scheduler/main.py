"""Scheduler process entrypoint -- Phase 1 INERT STUB.

daimon's real `main.py` polls due routines and dispatches headless MA turns:
it imports billing, defaults/provisioning, ma_resolver, headless_runner,
stores.domain/identity/routines, tenant_balance, usage_recording/sweep --
all multi-tenant/MA-provisioning machinery excluded by D-04 (see
01-RESEARCH.md's Architectural Responsibility Map: "Scheduler ... does
nothing in Phase 1 -- no ingestion job registered yet").

This stub exists so the package tree is present (D-04: "reused for
ingestion in Phase 3") and importable, WITHOUT pulling in any of that
excluded machinery. It is NOT wired into fly.toml's `[processes]` and is
NOT run this phase. Phase 3 replaces this file's body with the real Herald
match-ingestion polling loop (OpenDota discovery -> Stratz enrichment),
following this same signal-handling/liveness-responder shape.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import signal
import sys

import structlog
from daimon.adapters.scheduler.settings import SchedulerSettings
from daimon.core.config import load_settings
from daimon.core.health import start_liveness_responder
from daimon.core.logging_setup import configure_log_level

log = structlog.get_logger(__name__)


async def run(argv: list[str] | None = None) -> int:
    """Entrypoint. Returns the process exit code.

    Phase 1: no ingestion job is registered, so both `--once` and the
    long-running loop are no-ops beyond boot/liveness/shutdown -- there is
    nothing to tick yet. Kept runnable (not a bare `pass`) so the console
    script and liveness responder are exercised end-to-end when Phase 3
    wires a real tick.
    """
    parser = argparse.ArgumentParser(prog="daimon-scheduler")
    parser.add_argument("--once", action="store_true", help="Run exactly one tick and exit")
    args = parser.parse_args(argv)

    settings = load_settings()
    configure_log_level(settings.log.level)
    scheduler_settings = SchedulerSettings()

    log.info("scheduler.inert_stub.boot", reason="no Phase 1 ingestion job registered")

    if args.once:
        log.info("scheduler.inert_stub.tick_noop")
        return 0

    health_server = await start_liveness_responder(scheduler_settings.health_port)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    try:
        await stop_event.wait()
        return 0
    finally:
        health_server.close()
        await health_server.wait_closed()


def run_sync() -> None:
    """Console-script entrypoint. `daimon-scheduler` resolves here."""
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    run_sync()
