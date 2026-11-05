"""API tests for auth, RBAC and policy enforcement (no MCP / LLM calls needed)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def token(user):
    r = client.post("/api/auth/login", json={"username": user, "password": "Demo@123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_login_rejects_bad_password():
    assert client.post("/api/auth/login", json={"username": "hr.admin", "password": "wrong"}).status_code == 401


def test_me_requires_token_and_returns_persona():
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=token("employee")).json()["role"] == "employee"


def test_rbac_blocks_wrong_personas():
    emp = token("employee")
    assert client.get("/api/governance", headers=emp).status_code == 403
    assert client.get("/api/employees", headers=emp).status_code == 403
    assert client.post("/api/runs", json={"job_id": "X"}, headers=emp).status_code == 403
    assert client.get("/api/me/matches", headers=token("hiring.manager")).status_code == 403


def test_jd_precheck_flags_biased_language():
    r = client.post("/api/jobs/precheck", json={"title": "Dev", "description": "young rockstar wanted"}, headers=token("hiring.manager"))
    assert r.status_code == 200 and r.json()["decision"] == "warn"


def test_rejection_requires_reason():
    r = client.post("/api/runs/does-not-matter/review", headers=token("hiring.manager"),
                    json={"decisions": [{"employee_id": "EMP10001", "decision": "rejected", "reason": " "}]})
    assert r.status_code == 422
