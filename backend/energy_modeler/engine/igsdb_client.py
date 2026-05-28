"""LBNL IGSDB REST client (spec Ch 7.2).

Authenticated via IGSDB_API_TOKEN. In the beta the catalog is served from the
bundled snapshot (datastore.films); this client is used by the weekly sync job
to refresh optical/spectral data. All network calls degrade gracefully."""
from __future__ import annotations

from typing import Any

import httpx

from ..config import settings

BASE_URL = "https://igsdb.lbl.gov/api/v1"


class IGSDBClient:
    def __init__(self, token: str | None = None, timeout: float = 30.0):
        self.token = token or settings.igsdb_api_token
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self.token}", "Accept": "application/json"}

    def get_product(self, product_id: int) -> dict[str, Any] | None:
        """Fetch the full optical + thermal record for one product, or None."""
        if not self.available:
            return None
        try:
            resp = httpx.get(
                f"{BASE_URL}/products/{product_id}/",
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError):
            return None

    def search(self, manufacturer: str = "3M", subtype: str = "applied film") -> list[dict]:
        if not self.available:
            return []
        try:
            resp = httpx.get(
                f"{BASE_URL}/products/",
                params={
                    "type": "monolithic",
                    "manufacturer": manufacturer,
                    "subtype": subtype,
                    "per_page": 100,
                },
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except (httpx.HTTPError, ValueError):
            return []
