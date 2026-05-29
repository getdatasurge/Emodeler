#!/usr/bin/env python3
"""Fetch + verify the DOE Commercial Prototype Building IDFs (spec Ch 5.3 / 8.5).

Downloads the ASHRAE 90.1-2019 per-building-type zips from energycodes.gov and
extracts the per-city IDFs into
    $PROTOTYPES_DIR/ASHRAE901_2019/<BuildingType>/ASHRAE901_..._<City>.idf
where prototype_loader finds them (by the climate-zone's representative city).

    python scripts/fetch_prototypes.py                 # download + extract + manifest
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

STANDARD = "ASHRAE901_2019"
BASE_URL = "https://www.energycodes.gov/sites/default/files/2023-10"
UA = {"User-Agent": "Mozilla/5.0"}

# Our building_type id -> the DOE zip's type token.
BUILDING_TYPE_DOE = {
    "SmallOffice": "OfficeSmall",
    "MediumOffice": "OfficeMedium",
    "LargeOffice": "OfficeLarge",
    "PrimarySchool": "SchoolPrimary",
    "SecondarySchool": "SchoolSecondary",
    "StandaloneRetail": "RetailStandalone",
    "StripMall": "RetailStripmall",
    "Warehouse": "Warehouse",
}

ROOT = Path(__file__).resolve().parents[1]
_PROTO_ROOT = Path(os.getenv("PROTOTYPES_DIR") or (ROOT / "energy_modeler" / "data" / "prototypes"))
DEST = _PROTO_ROOT / STANDARD
MANIFEST = _PROTO_ROOT / f"{STANDARD}.manifest.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_type(building_type: str, doe_token: str) -> dict[str, str]:
    url = f"{BASE_URL}/ASHRAE901_{doe_token}_STD2019.zip"
    print(f"  {building_type}: {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        blob = resp.read()
    out_dir = DEST / building_type
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(BytesIO(blob)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".idf"):
                continue
            data = zf.read(name)
            out = out_dir / Path(name).name
            out.write_bytes(data)
            manifest[str(out.relative_to(DEST))] = _sha256(data)
    print(f"    -> {len(manifest)} IDFs", file=sys.stderr)
    return manifest


def main() -> int:
    manifest: dict[str, str] = {}
    failed = []
    for bt, token in BUILDING_TYPE_DOE.items():
        try:
            manifest.update(fetch_type(bt, token))
        except Exception as exc:  # noqa: BLE001
            print(f"  {bt}: FAILED {exc}", file=sys.stderr)
            failed.append(bt)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(
        f"Extracted {len(manifest)} IDFs across {len(BUILDING_TYPE_DOE) - len(failed)}"
        f"/{len(BUILDING_TYPE_DOE)} building types into {DEST}",
        file=sys.stderr,
    )
    return 1 if not manifest else 0


if __name__ == "__main__":
    raise SystemExit(main())
