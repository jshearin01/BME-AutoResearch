import os
os.environ["LLM_PROVIDER"] = "stub"  # hermetic tests: never spend real LLM calls
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


def test_full_run_skip_research():
    p = client.post("/api/projects", json={"title": "fullrun test", "problem": "one-hand opener"}).json()
    r = client.post("/api/agent/full-run", json={"project_id": p["id"], "brief": "grip block", "skip_research": True, "max_codegen_tries": 1})
    assert r.status_code == 200
    body = r.json()
    assert "research" in body and "spec" in body and "safety" in body and "codegen" in body
    assert body["stage"] in ("print", "cad", "design")


def test_full_run_async_job():
    import time
    p = client.post("/api/projects", json={"title": "async test", "problem": "grip"}).json()
    r = client.post("/api/agent/full-run-async", json={"project_id": p["id"], "brief": "grip block", "skip_research": True, "max_codegen_tries": 1})
    assert r.status_code == 200
    jid = r.json()["job_id"]
    # poll until done (stub LLM + local build are fast)
    for _ in range(30):
        j = client.get(f"/api/agent/jobs/{jid}").json()
        if j["status"] in ("done", "error"):
            break
        time.sleep(1)
    assert j["status"] == "done", j
    assert j["result"]["stage"] in ("print", "cad", "design")
    assert set(j["steps"]) == {"research", "spec", "safety", "codegen", "print"}
