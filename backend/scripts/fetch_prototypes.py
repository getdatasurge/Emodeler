#!/usr/bin/env python3
"""Fetch + verify the DOE Commercial Prototype Building IDFs (spec Ch 5.3 / 8.5).

Downloads the ASHRAE 90.1-2019 prototype set from energycodes.gov, extracts the
per (building type, climate zone) IDFs into
    energy_modeler/data/prototypes/ASHRAE901_2019/<BuildingType>/<CZ>.idf
and verifies them against a checked-in sha256 manifest so a build is reproducible.

Run inside an EnergyPlus-capable environment (the worker image) — the IDFs are
~50 MB and are bundled at image build time, not committed to git.

    python scripts/fetch_prototypes.py            # download + extract + verify
    python scripts/fetch_prototypes.py --write-manifest   # (re)generate manifest

NOTE: confirm SOURCE_URL against https://www.energycodes.gov/prototype-building-models
before a production build; PNNL re-issues the set per standard edition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

STANDARD = "ASHRAE901_2019"
SOURCE_URL = (
    "https://www.energycodes.gov/sites/default/files/2021-07/"
    "ASHRAE901_PrototypeBuildings_STD2019.zip"  # confirm against energycodes.gov
)
BUILDING_TYPES = [
    "SmallOffice", "MediumOffice", "LargeOffice",
    "PrimarySchool", "SecondarySchool",
    "StandaloneRetail", "StripMall", "Warehouse",
]

ROOT = Path(__file__).resolve().parents[1]
# Honor PROTOTYPES_DIR (the persistent disk in a deploy) so fetched IDFs land
# where prototype_loader looks and survive redeploys; else fall back in-repo.
_PROTO_ROOT = Path(os.getenv("PROTOTYPES_DIR") or (ROOT / "energy_modeler" / "data" / "prototypes"))
DEST = _PROTO_ROOT / STANDARD
MANIFEST = _PROTO_ROOT / f"{STANDARD}.manifest.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download_and_extract() -> dict[str, str]:
    """Download the prototype zip and extract the .idf files into DEST.

    Returns {relative_path: sha256} for every extracted IDF."""
    print(f"Downloading {SOURCE_URL} …", file=sys.stderr)
    with urllib.request.urlopen(SOURCE_URL, timeout=300) as resp:  # noqa: S310
        blob = resp.read()
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(BytesIO(blob)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".idf"):
                continue
            btype = next((b for b in BUILDING_TYPES if b.lower() in name.lower()), None)
            if btype is None:
                continue
            data = zf.read(name)
            out = DEST / btype / Path(name).name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            manifest[str(out.relative_to(DEST))] = _sha256(data)
    print(f"Extracted {len(manifest)} IDFs into {DEST}", file=sys.stderr)
    return manifest


def verify(manifest: dict[str, str]) -> bool:
    ok = True
    for rel, expected in manifest.items():
        path = DEST / rel
        if not path.exists():
            print(f"MISSING {rel}", file=sys.stderr)
            ok = False
            continue
        if _sha256(path.read_bytes()) != expected:
            print(f"HASH MISMATCH {rel}", file=sys.stderr)
            ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-manifest", action="store_true",
                    help="download, extract, and (re)write the sha256 manifest")
    args = ap.parse_args()

    manifest = download_and_extract()
    if args.write_manifest:
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        print(f"Wrote manifest with {len(manifest)} entries -> {MANIFEST}", file=sys.stderr)
        return 0

    if not MANIFEST.exists():
        print("No manifest to verify against; run with --write-manifest first.", file=sys.stderr)
        return 1
    expected = json.loads(MANIFEST.read_text())
    if verify(expected):
        print("Prototype IDFs verified against manifest.", file=sys.stderr)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
