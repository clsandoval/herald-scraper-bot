"""baseline

Empty-schema baseline migration — establishes the Alembic migration chain
head without creating any tables. Phase 1 has zero DATA-* requirements (no
match ingestion, no query/SQL agent, no scoring yet); `daimon.core._models.Base`
is intentionally empty (see `_models.py`). Domain tables are added by later
phases as new migrations against this same `Base`, chained on top of this
revision.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-01

"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op — empty schema baseline."""
    pass


def downgrade() -> None:
    """No-op — empty schema baseline."""
    pass
