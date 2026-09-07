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


def test_knowledge_ingest_query():
    i = client.post("/api/knowledge/ingest", json={"source": "test-note", "text": "PETG grip aid needs 2mm walls and gyroid infill for arthritis handle"})
    assert i.status_code == 200
    assert i.json()["chunks"] >= 1
    q = client.post("/api/knowledge/query", json={"query": "PETG walls arthritis handle", "limit": 3})
    assert q.status_code == 200
    assert len(q.json()["hits"]) >= 1


def test_cad_codegen_stub():
    p = client.post("/api/projects", json={"title": "codegen test", "problem": "grip aid"}).json()
    r = client.post("/api/cad/codegen", json={"project_id": p["id"], "brief": "small grip block 60x30x20mm"})
    assert r.status_code == 200
    body = r.json()
    assert "attempts" in body and len(body["attempts"]) >= 1
