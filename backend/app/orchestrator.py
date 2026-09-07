"""Orchestrator: routes problem -> research -> design -> safety -> cad -> print.

Keeps handoffs small + validated. Human gates enforced in UI (stage field).
Full-run endpoint chains all steps in one click (user explicitly overrides gates).
"""

import datetime
import json
import pathlib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.shared.db import get_db
from app.shared.observability import log_run
from app.shared.llm import generate
from app.modules.projects.models import Project

router = APIRouter(prefix="/api/agent", tags=["orchestrator"])


class Task(BaseModel):
    project_id: str
    goal: str  # e.g. "summarize need", "brainstorm concepts", "critique spec"
    context: str = ""


class FullRun(BaseModel):
    project_id: str
    brief: str = ""
    skip_research: bool = False  # skip live PubMed/Scholar (faster, offline)
    max_codegen_tries: int = 3


@router.post("/run")
async def run_task(task: Task, db: Session = Depends(get_db)):
    p = db.get(Project, task.project_id)
    title = p.title if p else task.project_id
    prompt = (f"Project: {title}\nStage: {p.stage if p else '?'}\n"
              f"Goal: {task.goal}\nContext: {task.context[:2000]}")
    out = await generate(prompt)
    log_run(db, task.project_id, "orchestrator", task.goal, task.context[:300], out[:800])
    # Suggest next stage, never auto-advance past gates
    next_hint = {"problem": "run research/search, then design/spec, then human approve",
                 "design": "run safety/check, then cad/generate, then human approve STL",
                 "cad": "run printing/packet"}.get(p.stage if p else "", "see stage checklist")
    return {"output": out, "next": next_hint}


@router.post("/full-run")
async def full_run(body: FullRun, db: Session = Depends(get_db)):
    """One click: research -> spec -> safety -> codegen -> validate -> packet."""
    from app.modules.knowledge.router import retrieve
    from app.modules.cad.router import validate_code, try_build_stl, _extract_code, CODEGEN_SYSTEM, CAD_DIR
    from app.modules.safety.router import HIGH_RISK

    p = db.get(Project, body.project_id)
    if not p:
        raise HTTPException(404, "project not found")
    brief = body.brief or f"{p.title}: {p.problem} | users: {p.users} | constraints: {p.constraints}"
    steps: dict = {"project_id": p.id}
    log_run(db, p.id, "orchestrator", "full-run.start", brief[:300], "pipeline started")

    # 1. Research (live search unless skipped)
    papers: list[dict] = []
    if not body.skip_research:
        try:
            from app.modules.research.router import pubmed_search, semanticscholar_search
            try:
                papers += await pubmed_search(f"{p.title} {p.problem}"[:200])
            except Exception as e:
                steps["research_error"] = f"pubmed: {e}"
            try:
                papers += await semanticscholar_search(f"{p.title} {p.problem}"[:200])
            except Exception as e:
                steps["research_error"] = (steps.get("research_error", "") + f" scholar: {e}").strip()
        except Exception as e:
            steps["research_error"] = str(e)
    kb = retrieve(db, brief, 4)
    synthesis = await generate(
        f"Query: {brief[:500]}\nPapers: {str(papers)[:2500]}\nKnowledge: {kb[:1500]}\n"
        "Summarize gaps, risks, 3 design implications with citations.")
    steps["research"] = {"papers": len(papers), "synthesis": synthesis[:2000]}
    p.stage = "evidence"
    db.commit()
    log_run(db, p.id, "orchestrator", "full-run.research", brief[:200], f"{len(papers)} papers", status="ok")

    # 2. Spec
    spec_text = await generate(
        f"PROJECT: {p.title}\nPROBLEM: {p.problem}\nUSERS: {p.users}\n"
        f"CONSTRAINTS: {p.constraints}\nKNOWLEDGE:\n{kb[:2000]}\nEVIDENCE:\n{synthesis[:1500]}\n\n"
        "Output: (1) 3 concepts scored on safety/printability/cost, "
        "(2) chosen spec: dimensions, loads, materials, tolerances, cleaning, failure modes, "
        "(3) open questions.")
    spec = {"concepts_text": spec_text,
            "dimensions_mm": {"max_envelope": [100, 100, 60]},
            "material_candidates": ["PLA", "PETG"], "min_wall_mm": 2.0,
            "status": "full-run draft — review before print"}
    p.spec_json = json.dumps(spec)
    p.stage = "design"
    db.commit()
    steps["spec"] = spec_text[:2000]
    log_run(db, p.id, "orchestrator", "full-run.spec", p.title, spec_text[:500])

    # 3. Safety (report, don't block — user overrode gates)
    text = f"{p.title} {p.problem} {spec_text[:1500]}"
    flags = sorted({w for w in HIGH_RISK if w in text.lower()})
    review = await generate(
        f"Design text: {text[:2000]}\nFlags: {flags}\n"
        "Output: risk class, biocompat/cleaning concerns, pre-print verifications, one-line disclaimer.")
    steps["safety"] = {"verdict": "BLOCKED — review required" if flags else "PASS with disclaimer",
                       "flags": flags, "review": review[:1500]}
    log_run(db, p.id, "orchestrator", "full-run.safety", text[:200],
            steps["safety"]["verdict"], status="ok" if not flags else "flagged")

    # 4. Codegen loop
    attempts: list[dict] = []
    stl_file = None
    code = ""
    last_err = ""
    tries = max(1, min(body.max_codegen_tries, 5))
    for i in range(tries):
        prompt = (f"DESIGN BRIEF: {brief}\nSPEC:\n{spec_text[:1500]}\nKNOWLEDGE:\n{kb[:1200]}\n"
                  + (f"PREVIOUS CODE FAILED: {last_err}\n{code[:2000]}\nFix it. " if last_err
                     else "Generate the part. ") + "Reply with one ```python block only.")
        raw = await generate(prompt, system=CODEGEN_SYSTEM, max_tokens=2000)
        code = _extract_code(raw)
        blocked = [x for x in validate_code(code) if x.startswith("blocked")]
        if blocked:
            last_err = "; ".join(blocked)
            attempts.append({"try": i + 1, "ok": False, "error": last_err})
            continue
        stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        py_path = CAD_DIR / f"{p.id}_full_{stamp}_t{i}.py"
        py_path.write_text(code)
        out_path = CAD_DIR / f"{p.id}_full_{stamp}_t{i}.stl"
        ok, note = try_build_stl(code, out_path)
        attempts.append({"try": i + 1, "ok": ok, "note": note,
                         "stl_file": str(out_path) if ok else None})
        if ok:
            stl_file = str(out_path)
            break
        last_err = note
    steps["codegen"] = {"ok": stl_file is not None, "attempts": attempts,
                        "stl_file": stl_file}
    if stl_file:
        p.stage = "cad"
        db.commit()
    log_run(db, p.id, "orchestrator", "full-run.codegen", brief[:200],
            f"stl={stl_file}", status="ok" if stl_file else "failed")

    # 5. Validate + packet
    if stl_file:
        try:
            import trimesh
            m = trimesh.load(stl_file)
            steps["validate"] = {"watertight": bool(m.is_watertight),
                                 "volume_mm3": float(m.volume) if m.is_volume else None,
                                 "faces": int(len(m.faces)),
                                 "bbox_mm": m.bounds.tolist()}
        except Exception as e:
            steps["validate"] = {"note": f"trimesh check skipped/failed: {e}"}
        from app.modules.printing.router import find_slicer
        steps["packet"] = {
            "stl_file": stl_file, "slicer_found": find_slicer(),
            "recommended": {"slicer": "OrcaSlicer (FOSS)", "material": "PETG",
                            "layer_mm": 0.2, "walls": 3, "infill": "20% gyroid"},
            "preflight": ["watertight STL", "min wall >=2mm",
                          "orient flat, brim if small", "log filament lot",
                          "NOT FOR CLINICAL USE"],
            "disclaimer": "Research prototype only. Not a medical device."}
        p.stage = "print"
        db.commit()
    steps["stage"] = p.stage
    log_run(db, p.id, "orchestrator", "full-run.done", "", f"stage={p.stage} stl={stl_file}")
    return steps
