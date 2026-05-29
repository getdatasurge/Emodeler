"""Runtime configuration. Secrets come from the environment (never the repo)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def _env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name, default)
    return val if val else default


class Settings:
    # Upstream API credentials (optional in beta; integrations fall back to
    # bundled offline data when absent — see engine/weather.py, carbon.py).
    nrel_api_key: str | None = _env("NREL_API_KEY")
    igsdb_api_token: str | None = _env("IGSDB_API_TOKEN")

    # Supabase auth (spec Ch 1.1). When unset, the API runs in permissive
    # single-tenant beta mode (no token required). Set AUTH_ENFORCED=true plus
    # SUPABASE_JWT_SECRET to require a valid bearer JWT on protected routes.
    supabase_url: str | None = _env("SUPABASE_URL")
    supabase_jwt_secret: str | None = _env("SUPABASE_JWT_SECRET")
    auth_enforced: bool = (_env("AUTH_ENFORCED", "false") or "false").lower() in (
        "1",
        "true",
        "yes",
    )

    # Error/observability. Sentry is a no-op unless SENTRY_DSN is set.
    sentry_dsn: str | None = _env("SENTRY_DSN")

    # Cloudflare R2 (S3-compatible) for audit bundles (spec Ch 11). When unset,
    # bundles are served from local storage_dir instead of a signed URL.
    r2_endpoint: str | None = _env("R2_ENDPOINT")
    r2_access_key_id: str | None = _env("R2_ACCESS_KEY_ID")
    r2_secret_access_key: str | None = _env("R2_SECRET_ACCESS_KEY")
    r2_bucket: str | None = _env("R2_BUCKET")

    # EnergyPlus binary. When present the real IDF pipeline runs; otherwise the
    # engine emits a clearly-labeled analytical estimate (NOT for bid use).
    energyplus_dir: str | None = _env("ENERGYPLUS_DIR")

    prototypes_dir: str | None = _env("PROTOTYPES_DIR")
    egrid_data_dir: str | None = _env("EGRID_DATA_DIR")

    # When set (the EnergyPlus worker stack), the API enqueues calc jobs to the
    # Celery worker instead of running them inline via BackgroundTasks.
    redis_url: str | None = _env("REDIS_URL")

    # Where run working dirs + the audit bundle are written.
    storage_dir: Path = Path(_env("STORAGE_DIR", "./storage") or "./storage")

    database_url: str = _env("DATABASE_URL", "sqlite:///./energy_modeler.db")

    @property
    def energyplus_exe(self) -> str | None:
        """Resolve the EnergyPlus executable, or None if unavailable."""
        if self.energyplus_dir:
            cand = Path(self.energyplus_dir) / "energyplus"
            if cand.exists():
                return str(cand)
        for name in ("energyplus", "energyplus-22.1.0", "EnergyPlus"):
            found = shutil.which(name)
            if found:
                return found
        return None


settings = Settings()
