"""ZIP-lookup cache (spec Ch 10.4 / build §5.3): 30-day TTL over zip_lookup_cache.

Keeps repeat PVWatts / URDB calls to one per ZIP per 30 days. Errors are never
cached — the producer raises straight through."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .models import ZipLookupCache

TTL = timedelta(days=30)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_or_set(
    session: Session, zip_code: str, kind: str, producer: Callable[[], dict]
) -> tuple[dict, bool]:
    """Return (payload, cache_hit). Calls `producer` only on miss/expiry."""
    row = (
        session.query(ZipLookupCache)
        .filter_by(zip=zip_code, kind=kind)
        .order_by(ZipLookupCache.fetched_at.desc())
        .first()
    )
    if row and row.fetched_at and datetime.now(timezone.utc) - _aware(row.fetched_at) < TTL:
        return row.payload, True

    payload = producer()  # may raise (e.g. 404) — intentionally not cached
    session.add(ZipLookupCache(zip=zip_code, kind=kind, payload=payload))
    session.commit()
    return payload, False
