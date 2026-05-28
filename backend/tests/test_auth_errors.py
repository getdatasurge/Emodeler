"""Week 01 foundations: standard error envelope + (permissive/enforced) auth."""
import jwt

from energy_modeler.config import settings


def test_error_envelope_shape(client):
    r = client.get("/api/projects/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "NOT_FOUND"
    assert body["error"]
    assert body["request_id"].startswith("req_")
    assert body["details"]["project_id"] == "does-not-exist"
    assert r.headers.get("X-Request-ID")


def test_permissive_auth_default(client):
    # Beta default (AUTH_ENFORCED unset): protected routes work with no token.
    assert client.get("/api/projects").status_code == 200


def test_enforced_auth_rejects_then_accepts(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_enforced", True)
    monkeypatch.setattr(settings, "supabase_jwt_secret", "testsecret")

    # No token -> 401 with the auth envelope.
    r = client.get("/api/projects")
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_REQUIRED"

    # Garbage token -> 401.
    bad = client.get("/api/projects", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401

    # Valid Supabase-style HS256 token -> 200.
    token = jwt.encode(
        {"sub": "user-1", "aud": "authenticated", "email": "a@b.com"},
        "testsecret",
        algorithm="HS256",
    )
    ok = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200

    # Health stays open even under enforcement.
    assert client.get("/api/health").status_code == 200
