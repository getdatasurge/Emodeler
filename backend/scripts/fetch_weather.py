#!/usr/bin/env python3
"""Fetch TMY3 .epw weather files for the EnergyPlus worker (spec Ch 8.1).

Resolves each project ZIP -> nearest station via the bundled crosswalk, then
downloads that station's EPW into <STORAGE_DIR>/weather/<station_id>.epw, where
engine/weather.py:epw_for_zip looks for it.

EPW source: set WEATHER_BASE_URL to your EPW host. The canonical free TMY3 set
is climate.onebuilding.org / energyplus.net/weather; NSRDB PSM3 (developer.nrel.gov)
can also be downloaded and converted. Confirm the URL pattern for your source.

    python scripts/fetch_weather.py 33540 55303 80921      # specific ZIPs
    python scripts/fetch_weather.py --all                  # every ZIP in the crosswalk
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from energy_modeler import datastore  # noqa: E402
from energy_modeler.config import settings  # noqa: E402

WEATHER_BASE_URL = os.getenv("WEATHER_BASE_URL", "").rstrip("/")


def _dest_dir() -> Path:
    d = Path(settings.storage_dir) / "weather"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch_zip(zip_code: str) -> bool:
    z = datastore.get_zip(zip_code)
    if not z:
        print(f"  {zip_code}: not in crosswalk", file=sys.stderr)
        return False
    station = z["station_id"]
    out = _dest_dir() / f"{station}.epw"
    if out.exists():
        print(f"  {zip_code} -> {station}.epw (cached)", file=sys.stderr)
        return True
    if not WEATHER_BASE_URL:
        print(
            f"  {zip_code} -> need {station}.epw; set WEATHER_BASE_URL to your EPW host",
            file=sys.stderr,
        )
        return False
    url = f"{WEATHER_BASE_URL}/{station}.epw"
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310
            out.write_bytes(resp.read())
        print(f"  {zip_code} -> {station}.epw ({out.stat().st_size // 1024} KB)", file=sys.stderr)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  {zip_code} -> {station}.epw FAILED: {exc}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("zips", nargs="*", help="ZIP codes to fetch")
    ap.add_argument("--all", action="store_true", help="fetch every ZIP in the crosswalk")
    args = ap.parse_args()

    zips = list(datastore.zip_crosswalk().keys()) if args.all else args.zips
    if not zips:
        ap.error("pass ZIP codes or --all")
    ok = sum(fetch_zip(z) for z in zips)
    print(f"Fetched/cached {ok}/{len(zips)} weather files into {_dest_dir()}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
