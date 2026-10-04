"""SQLAlchemy 2.0 ORM base for daimon-core.

This module owns the schema. Alembic's `env.py` reads `Base.metadata` from here.

Phase 1 has zero DATA-* requirements (no match ingestion, no query/SQL agent,
no scoring yet) — `Base` is intentionally empty. Domain tables are added by
later phases against this same `Base`, keeping the baseline Alembic migration
trivially safe.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all daimon-core ORM models."""
