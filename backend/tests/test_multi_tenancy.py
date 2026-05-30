"""Multi-tenancy: a project belongs to an org (DEFAULT_ORG_ID in the beta;
the JWT-resolved org_id when AUTH_ENFORCED=true). The list / get / patch /
add-face endpoints scope by it; with AUTH_ENFORCED off, every caller still
sees the default org so the beta deploy is unchanged."""
import pytest
from fastapi.testclient import TestClient

from app.auth import Identity, require_auth
from app.main import app
from app.models import DEFAULT_ORG_ID


def _seed_project(c: TestClient, name: str) -> str:
    body = {
        "name": name, "zip": "33540", "building_type": "MediumOffice",
        "gross_floor_area_sf": 14500,
    }
    resp = c.post("/api/projects", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture
def override_identity():
    """Yield a setter that swaps the require_auth Identity for a test, and
    restores the override on teardown."""
    original = app.dependency_overrides.get(require_auth)

    def _set(identity: Identity) -> None:
        app.dependency_overrides[require_auth] = lambda: identity

    try:
        yield _set
    finally:
        if original is None:
            app.dependency_overrides.pop(require_auth, None)
        else:
            app.dependency_overrides[require_auth] = original


def test_default_org_constant_stable():
    """The default org id is part of the schema's default; if this ever
    changes, the in-place migration story changes too."""
    assert DEFAULT_ORG_ID == "00000000-0000-0000-0000-000000000001"


def test_single_tenant_beta_lists_and_reads_default_org(client):
    """No identity override -> the default beta identity (DEV_IDENTITY_USER
    on DEFAULT_ORG_ID). Lists return at least the seeded demo project."""
    listed = client.get("/api/projects").json()
    assert isinstance(listed, list)
    # At least the seeded demo project is visible to the default identity.
    assert len(listed) >= 1
    first = listed[0]["id"]
    assert client.get(f"/api/projects/{first}").status_code == 200


def test_create_project_stamps_caller_org_id(client, override_identity):
    """A project created under org X is stamped with X.org_id (visible only
    to org X going forward)."""
    override_identity(Identity(user_id="acme-pm", org_id="org-acme"))
    pid = _seed_project(client, "Acme HQ retrofit")
    from app.db import SessionLocal
    from app.models import Project as P
    with SessionLocal() as sess:
        assert sess.get(P, pid).org_id == "org-acme"


def test_other_org_cannot_see_or_mutate_anothers_project(client, override_identity):
    """Org A creates a project; Org B then must not list it, read it, patch
    it, or add a face to it. 404 (not 403) — don't leak existence."""
    override_identity(Identity(user_id="acme-pm", org_id="org-acme"))
    pid = _seed_project(client, "Acme HQ retrofit")
    # Switch identity.
    override_identity(Identity(user_id="rival-pm", org_id="org-rival"))
    listed = client.get("/api/projects").json()
    assert all(p["id"] != pid for p in listed)
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert client.patch(f"/api/projects/{pid}", json={"name": "Stolen"}).status_code == 404
    face = {"orientation": "S", "area_sqft": 100, "base_glazing_id": "dbl_clear_3mm_13mmAir"}
    assert client.post(f"/api/projects/{pid}/faces", json=face).status_code == 404


def test_listing_filters_to_current_org_only(client, override_identity):
    """Two orgs, two projects; each sees only its own."""
    override_identity(Identity(user_id="a-pm", org_id="org-A"))
    pid_a = _seed_project(client, "Project A")
    override_identity(Identity(user_id="b-pm", org_id="org-B"))
    pid_b = _seed_project(client, "Project B")

    # Org A sees A but not B.
    override_identity(Identity(user_id="a-pm", org_id="org-A"))
    ids = {p["id"] for p in client.get("/api/projects").json()}
    assert pid_a in ids and pid_b not in ids

    # Org B sees B but not A.
    override_identity(Identity(user_id="b-pm", org_id="org-B"))
    ids = {p["id"] for p in client.get("/api/projects").json()}
    assert pid_b in ids and pid_a not in ids
