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

    # EnergyPlus binary. When present the real IDF pipeline runs; otherwise the
    # engine emits a clearly-labeled analytical estimate (NOT for bid use).
    energyplus_dir: str | None = _env("ENERGYPLUS_DIR")

    prototypes_dir: str | None = _env("PROTOTYPES_DIR")
    egrid_data_dir: str | None = _env("EGRID_DATA_DIR")

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
        for name in ("energyplus", "energyplus-24.2.0", "EnergyPlus"):
            found = shutil.which(name)
            if found:
                return found
        return None


settings = Settings()
