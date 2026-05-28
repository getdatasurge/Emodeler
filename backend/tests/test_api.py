"""End-to-end API tests. Starlette's TestClient runs BackgroundTasks
synchronously after the response, so a calc job completes before the poll."""


def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert "engine_mode" in meta and "energyplus_available" in meta


def test_films_catalog(client):
    films = client.get("/api/films").json()
    assert len(films) == 16
    skus = {f["sku"] for f in films}
    assert "3M-PR40X" in skus
    one = client.get("/api/films/3M-PR40X").json()
    assert one["shgc_on_dbl_clear"] == 0.23


def test_pairing_lookup(client):
    p = client.get("/api/films/3M-PR40X/pairings/dbl_clear_3mm_13mmAir").json()
    assert 0 < p["shgc"] < p["base_shgc"]


def test_zip_lookups(client):
    assert client.get("/api/climate-zone/33540").json()["climate_zone"] == "2A"
    assert client.get("/api/egrid/33540").json()["subregion"] == "FRCC"
    solar = client.get("/api/solar/33540").json()
    assert "poa_monthly_kwh_m2" in solar
    assert client.get("/api/utility/33540").json()["avg_energy_rate_usd_kwh"] > 0


def test_demo_project_seeded(client):
    projects = client.get("/api/projects").json()
    assert any("Zephyrhills" in p["name"] for p in projects)


def test_full_calc_flow(client):
    created = client.post("/api/projects", json={
        "name": "API Test Office", "zip": "33540", "building_type": "MediumOffice",
        "gross_floor_area_sf": 14500,
        "faces": [
            {"orientation": "S", "area_sqft": 900, "base_glazing_id": "dbl_clear_3mm_13mmAir"},
            {"orientation": "N", "area_sqft": 900, "base_glazing_id": "dbl_clear_3mm_13mmAir"},
        ],
    }).json()
    assert created["climate_zone"] == "2A"  # auto-filled from ZIP
    assert created["egrid_subregion"] == "FRCC"

    run = client.post("/api/calc/run", json={
        "project_id": created["id"],
        "scenarios": [{"label": "Good", "film_sku": "3M-PR40X", "installed_cost_usd": 30000}],
    })
    assert run.status_code == 202
    job_id = run.json()["job_id"]

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert len(job["scenario_results"]) == 1
    assert job["scenario_results"][0]["delta_cost_usd_per_year"] > 0

    # Audit bundle + report render.
    assert client.get(f"/api/jobs/{job_id}/audit-bundle").status_code == 200
    report = client.get(f"/api/reports/{job_id}")
    assert report.status_code == 200 and "Energy Savings" in report.text


def test_calc_requires_faces(client):
    created = client.post("/api/projects", json={
        "name": "No Faces", "zip": "33540", "building_type": "SmallOffice",
        "gross_floor_area_sf": 5000,
    }).json()
    run = client.post("/api/calc/run", json={
        "project_id": created["id"],
        "scenarios": [{"label": "Good", "film_sku": "3M-PR40X", "installed_cost_usd": 10000}],
    })
    assert run.status_code == 422
