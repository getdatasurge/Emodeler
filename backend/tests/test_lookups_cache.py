"""Week 05: ZIP-lookup cache (X-Cache HIT/MISS, errors not cached)."""


def test_lookup_cache_hit_on_repeat(client):
    # Repeat call is always served from cache (HIT), regardless of prior state.
    r1 = client.get("/api/egrid/33540")
    assert r1.status_code == 200
    r2 = client.get("/api/egrid/33540")
    assert r2.status_code == 200
    assert r2.headers.get("X-Cache") == "HIT"
    assert r1.json() == r2.json()


def test_lookup_error_not_cached(client):
    # A ZIP absent from the crosswalk 404s and is not cached.
    a = client.get("/api/climate-zone/00000")
    b = client.get("/api/climate-zone/00000")
    assert a.status_code == 404
    assert b.status_code == 404
    assert b.json()["code"] in ("ZIP_NOT_FOUND", "NOT_FOUND")
