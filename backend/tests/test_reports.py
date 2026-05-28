"""Week 10: branded report — HTML (always) + server-side PDF (where libs exist)."""
import pytest


def _completed_job_id(client) -> str:
    projs = client.get("/api/projects").json()
    pid = next(p["id"] for p in projs if p["status"] == "completed")  # the pre-run demo
    return client.get(f"/api/projects/{pid}/results").json()["job_id"]


def test_html_report_has_assumptions_section(client):
    job_id = _completed_job_id(client)
    r = client.get(f"/api/reports/{job_id}")
    assert r.status_code == 200
    assert "Modeling Assumptions" in r.text
    assert "Cooling COP" in r.text


def _weasyprint_ok() -> bool:
    try:
        from weasyprint import HTML

        HTML(string="<p>x</p>").write_pdf()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _weasyprint_ok(), reason="WeasyPrint native libs unavailable")
def test_pdf_report_renders(client):
    job_id = _completed_job_id(client)
    r = client.get(f"/api/reports/{job_id}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_audit_bundle_served_locally_without_r2(client):
    # R2 unconfigured in tests -> the .zip is served from local storage.
    job_id = _completed_job_id(client)
    r = client.get(f"/api/jobs/{job_id}/audit-bundle")
    assert r.status_code == 200
    assert "zip" in r.headers.get("content-type", "")
