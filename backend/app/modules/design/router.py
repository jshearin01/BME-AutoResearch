"""Designer: need -> spec + concepts. Writes spec_json back to project."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from app.shared.db import get_db
from app.shared.observability import log_run
from app.shared.llm import generate
from app.modules.projects.models import Project

router = APIRouter(prefix="/api/design", tags=["design"])


@router.post("/spec")
async def make_spec(body: dict, db: Session = Depends(get_db)):
    pid = body.get("project_id", "")
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    try:
        from app.modules.knowledge.router import retrieve
        kb = retrieve(db, f"{p.title} {p.problem} {p.constraints}", 4)
    except Exception:
        kb = ""
    prompt = (f"PROJECT: {p.title}\nPROBLEM: {p.problem}\nUSERS: {p.users}\n"
              f"CONSTRAINTS: {p.constraints}\nKNOWLEDGE:\n{kb[:2000]}\n\n"
              "Output: (1) 3 concepts scored on safety/printability/cost, "
              "(2) chosen concept spec: dimensions, loads, materials, tolerances, "
              "cleaning, failure modes, (3) open questions for human gate.")
    text = await generate(prompt)
    spec = {"concepts_text": text, "dimensions_mm": {"max_envelope": [100, 100, 60]},
            "material_candidates": ["PLA", "PETG"], "min_wall_mm": 1.2,
            "status": "draft — needs human approval"}
    p.spec_json = json.dumps(spec)
    p.stage = "design"
    db.commit()
    log_run(db, pid, "designer", "design.spec", f"{p.title} || {prompt[:1500]}", text[:2000])
    return {"project_id": pid, "spec": spec, "raw": text, "prompt": prompt}
