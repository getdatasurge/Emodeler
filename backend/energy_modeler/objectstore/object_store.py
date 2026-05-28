"""Audit-bundle object storage on Cloudflare R2 (S3-compatible) — spec Ch 11.

Entirely optional: when R2 env vars are unset, every function no-ops and the API
serves the bundle from local storage_dir instead. boto3 is imported lazily so
the slim API image doesn't pay for it unless R2 is actually configured."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from ..config import settings


def enabled() -> bool:
    return bool(
        settings.r2_bucket
        and settings.r2_endpoint
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
    )


def audit_key(job_id: str) -> str:
    return f"audit/{job_id}.zip"


def _client():
    import boto3  # lazy: only needed when R2 is configured

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def upload_file(local_path: Path, key: str) -> str | None:
    """Upload a file to R2. Returns the object key, or None when R2 is disabled."""
    if not enabled():
        return None
    _client().upload_file(str(local_path), settings.r2_bucket, key)
    return key


def signed_url(key: str, ttl_days: int = 7) -> str | None:
    """Pre-signed GET URL (7-day default TTL), or None when R2 is disabled."""
    if not enabled():
        return None
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket, "Key": key},
        ExpiresIn=int(timedelta(days=ttl_days).total_seconds()),
    )
