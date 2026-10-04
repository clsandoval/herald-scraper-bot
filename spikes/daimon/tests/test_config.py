"""Import-smoke + config-from-env test for daimon-core.

No hardcoded secrets: all values come from `monkeypatch.setenv` fixtures.
Asserts the Phase-1-trimmed `Settings` shape, `SecretStr` protection on
`bot_token`/`api_key` (D-11 — no plaintext secrets in log/repr), the empty
`Base.metadata` (Phase 1 has no domain schema), and that the inert `turn/` +
`skills/` engine imports cleanly (self-consistent dependency graph: ma.py,
errors.py, tenacity, httpx are all present).
"""

from __future__ import annotations

import pytest


def test_config_imports() -> None:
    from daimon.core.config import Settings, load_settings  # noqa: F401


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from daimon.core.config import Settings

    monkeypatch.setenv("DAIMON_DATABASE__URL", "postgresql+asyncpg://user:pw@localhost/db")
    monkeypatch.setenv("DAIMON_ANTHROPIC__API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setenv("DAIMON_DISCORD__BOT_TOKEN", "fake-discord-token-value")

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert str(settings.database.url).startswith("postgresql+asyncpg://")
    assert settings.anthropic.api_key.get_secret_value() == "sk-test-not-a-real-key"
    assert settings.discord is not None
    assert settings.discord.bot_token.get_secret_value() == "fake-discord-token-value"

    # SecretStr must not leak the raw value via repr/str.
    assert "fake-discord-token-value" not in repr(settings.discord.bot_token)
    assert "sk-test-not-a-real-key" not in repr(settings.anthropic.api_key)


def test_empty_models_base() -> None:
    from daimon.core._models import Base

    assert len(Base.metadata.tables) == 0


def test_turn_and_skills_import_cleanly() -> None:
    """Inert-engine smoke: turn/ + skills/ must import with no Phase-1 caller."""
    import daimon.core.skills  # noqa: F401
    import daimon.core.turn  # noqa: F401
    from daimon.core.turn import gating

    assert gating.should_admit_turn(current_in_flight=0, cap=1) is True
    assert gating.should_admit_turn(current_in_flight=1, cap=1) is False
