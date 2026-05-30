"""Database engine + session (spec Ch 9.3).

Beta defaults to SQLite so the platform runs with zero external infra. In
production DATABASE_URL points at Supabase/Postgres; the ORM models and the
canonical Postgres DDL (db/schema.sql) carry org_id on every user-data table so
the multi-tenant migration (Phase 4) is an RLS policy change, not a schema one."""
from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from energy_modeler.config import settings

log = logging.getLogger(__name__)

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

# Idempotent micro-migrations. Base.metadata.create_all only creates tables
# that don't exist; it does NOT add new columns to existing tables. Until a
# real migration tool lands, each entry here applies an ADD COLUMN at startup
# when the column is missing (nullable + no default, so existing rows survive).
# Drop entries once you cut a real Alembic migration.
_PENDING_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("projects", "gas_rate_usd_therm", "FLOAT"),
    ("projects", "hvac_fan_kw_per_cfm", "FLOAT"),
    ("projects", "hvac_economizer_high_limit_f", "FLOAT"),
)


class Base(DeclarativeBase):
    pass


def _apply_pending_columns() -> None:
    is_sqlite = settings.database_url.startswith("sqlite")
    with engine.begin() as conn:
        for table, column, type_sql in _PENDING_COLUMNS:
            try:
                if is_sqlite:
                    existing = {
                        row[1] for row in conn.exec_driver_sql(
                            f"PRAGMA table_info({table})"
                        )
                    }
                else:
                    existing = {
                        row[0] for row in conn.exec_driver_sql(
                            "SELECT column_name FROM information_schema.columns "
                            f"WHERE table_name = '{table}'"
                        )
                    }
                if column in existing:
                    continue
                conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {column} {type_sql}"
                )
                log.info("Added missing column %s.%s", table, column)
            except Exception as exc:  # noqa: BLE001 - never block startup
                log.warning("Skipping migration for %s.%s: %s", table, column, exc)


def init_db() -> None:
    from . import models  # noqa: F401 - register mappers

    Base.metadata.create_all(engine)
    _apply_pending_columns()


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
