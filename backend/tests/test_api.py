from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_projects_seed_and_create():
    r = client.get("/api/projects")
    assert r.status_code == 200
    assert len(r.json()) >= 1
    c = client.post("/api/projects", json={"title": "test splint", "problem": "x"})
    assert c.status_code == 200
    assert c.json()["id"]
