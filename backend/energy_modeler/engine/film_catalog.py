"""3M film SKU -> optical spec resolution (spec Ch 5/7).

A 3M film is catalogued in IGSDB as a complete glass+film monolithic system, not
a standalone layer. resolve() returns the bundled curated record; when an IGSDB
token is configured the optical block can be refreshed live via igsdb_client."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import datastore


@dataclass
class FilmSpec:
    sku: str
    display_name: str
    product_line: str
    igsdb_product_id: int
    shgc_on_dbl_clear: float
    tvis_pct: float
    warranty_yrs: int | None
    thickness_mil: float | None
    optical: dict[str, Any] = field(default_factory=dict)


def resolve(sku: str) -> FilmSpec:
    rec = datastore.get_film(sku)
    if rec is None:
        raise KeyError(f"Unknown film SKU: {sku!r}")
    return FilmSpec(
        sku=rec["sku"],
        display_name=rec["display_name"],
        product_line=rec["product_line"],
        igsdb_product_id=rec["igsdb_product_id"],
        shgc_on_dbl_clear=float(rec["shgc_on_dbl_clear"]),
        tvis_pct=float(rec["tvis_pct"]),
        warranty_yrs=rec.get("warranty_yrs"),
        thickness_mil=rec.get("thickness_mil"),
        optical=dict(rec.get("optical", {})),
    )
