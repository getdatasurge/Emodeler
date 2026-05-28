"""Database engine + session (spec Ch 9.3).

Beta defaults to SQLite so the platform runs with zero external infra. In
production DATABASE_URL points at Supabase/Postgres; the ORM models and the
canonical Postgres DDL (db/schema.sql) carry org_id on every user-data table so
the multi-tenant migration (Phase 4) is an RLS policy change, not a schema one."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from energy_modeler.config import settings

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from . import models  # noqa: F401 - register mappers

    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
