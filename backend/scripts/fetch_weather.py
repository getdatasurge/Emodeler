#!/usr/bin/env python3
"""Fetch TMY3 .epw weather for the EnergyPlus worker (spec Ch 8.1).

Downloads the energycodes.gov weather bundle (the representative-city TMY3 set
that matches the DOE prototypes) and extracts every .epw into
$STORAGE_DIR/weather, where engine/weather.py:epw_for_zip resolves a project's
climate zone -> representative city -> .epw.

    python scripts/fetch_weather.py
"""
from __future__ import annotations

import sys
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from energy_modeler.config import settings  # noqa: E402

EPW_BUNDLE_URL = "https://www.energycodes.gov/sites/default/files/2021-05/IECC_epw.zip"
UA = {"User-Agent": "Mozilla/5.0"}


def main() -> int:
    dest = Path(settings.storage_dir) / "weather"
    dest.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {EPW_BUNDLE_URL} …", file=sys.stderr)
    req = urllib.request.Request(EPW_BUNDLE_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        blob = resp.read()
    n = 0
    with zipfile.ZipFile(BytesIO(blob)) as zf:
        for name in zf.namelist():
            if name.lower().endswith(".epw"):
                (dest / Path(name).name).write_bytes(zf.read(name))
                n += 1
    print(f"Extracted {n} .epw files into {dest}", file=sys.stderr)
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
