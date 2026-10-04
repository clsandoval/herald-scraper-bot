"""Offline checks for the collaborator-facing mode and container boundaries."""
import importlib.util
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest


def test_reporter_import_ignores_invalid_menu_settings(monkeypatch, tmp_path):
    for setting in ("DUR_MIN", "KPM_MIN", "MAX_PAGES", "STRATZ_BATCH",
                    "RETENTION_DAYS", "STRATZ_DAILY_BUDGET", "SWING_MIN"):
        monkeypatch.setenv(setting, "invalid-menu-only-setting")
    monkeypatch.setenv("HERALD_DB", str(tmp_path / "must-not-create.db"))
    result = subprocess.run(
        [sys.executable, "-c", "import sys; from herald import scheduled; "
         "assert 'herald.ingest' not in sys.modules; "
         "assert scheduled.MIN_DURATION == 4500"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("uid", [0, 1000])
def test_container_prepares_only_mount_and_executes_unprivileged(monkeypatch, uid):
    path = Path(__file__).resolve().parents[1] / "docker" / "entrypoint.py"
    spec = importlib.util.spec_from_file_location("container_entrypoint", path)
    entrypoint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entrypoint)
    calls = []
    monkeypatch.setattr(entrypoint.os, "geteuid", lambda: uid)
    for method in ("chown", "setgroups", "setgid", "setuid", "execvp"):
        monkeypatch.setattr(entrypoint.os, method, Mock(
            side_effect=lambda *args, name=method: calls.append((name, args))))
    monkeypatch.setattr(entrypoint.sys, "argv", [str(path), "python", "-m", "herald"])
    entrypoint.main()
    expected = [] if uid else [
        ("chown", ("/data", 1000, 1000)), ("setgroups", ([],)),
        ("setgid", (1000,)), ("setuid", (1000,)),
    ]
    assert calls == [*expected, ("execvp", ("python", ["python", "-m", "herald"]))]
