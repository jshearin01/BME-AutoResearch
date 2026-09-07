"""Orchestrator: routes problem -> research -> design -> safety -> cad -> print.

Keeps handoffs small + validated. Human gates enforced in UI (stage field).
Full-run chains all steps; async variant reports live progress per step for polling.
"""

import asyncio
import datetime
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.shared.db import get_db, SessionLocal
from app.shared.observability import log_run
from app.shared.llm import generate
from app.modules.projects.models import Project

router = APIRouter(prefix="/api/agent", tags=["orchestrator"])

STEP_ORDER = ["research", "spec", "safety", "codegen", "print"]


class Task(BaseModel):
    project_id: str
    goal: str  # e.g. "summarize need", "brainstorm concepts", "critique spec"
    context: str = ""


class FullRun(BaseModel):
    project_id: str
    brief: str = ""
    skip_research: bool = False  # skip live PubMed/Scholar (faster, offline)
    max_codegen_tries: int = 3


# In-memory job registry (single-process dev server). Each job:
# {status, current, steps: {name: {status, detail}}, result, error, timestamps}
jobs: dict[str, dict] = {}


def _fresh_steps() -> dict:
    return {name: {"status": "pending", "detail": ""} for name in STEP_ORDER}


@router.post("/run")
async def run_task(task: Task, db: Session = Depends(get_db)):
    p = db.get(Project, task.project_id)
    title = p.title if p else task.project_id
    prompt = (f"Project: {title}\nStage: {p.stage if p else '?'}\n"
              f"Goal: {task.goal}\nContext: {task.context[:2000]}")
    out = await generate(prompt)
    log_run(db, task.project_id, "orchestrator", task.goal, task.context[:300], out[:800])
    next_hint = {"problem": "run research/search, then design/spec, then human approve",
                 "design": "run safety/check, then cad/generate, then human approve STL",
                 "cad": "run printing/packet"}.get(p.stage if p else "", "see stage checklist")
    return {"output": out, "next": next_hint}


async def _pipeline(db: Session, body: FullRun, report=None):
    """Shared pipeline. report(step, status, detail) called on every transition."""
    from app.modules.knowledge.router import retrieve
    from app.modules.cad.router import validate_code, try_build_stl, _extract_code, CODEGEN_SYSTEM, CAD_DIR
    from app.modules.safety.router import HIGH_RISK

    def mark(step, status, detail=""):
        if report:
            report(step, status, detail)

    p = db.get(Project, body.project_id)
    if not p:
        raise HTTPException(404, "project not found")
    brief = body.brief or f"{p.title}: {p.problem} | users: {p.users} | constraints: {p.constraints}"
    steps: dict = {"project_id": p.id}
    log_run(db, p.id, "orchestrator", "full-run.start", brief[:300], "pipeline started")

    # 1. Research (live search unless skipped)
    mark("research", "running", "searching PubMed + Semantic Scholar")
    papers: list[dict] = []
    if not body.skip_research:
        try:
            from app.modules.research.router import pubmed_search, semanticscholar_search
            try:
                mark("research", "running", "searching PubMed")
                papers += await pubmed_search(f"{p.title} {p.problem}"[:200])
            except Exception as e:
                steps["research_error"] = f"pubmed: {e}"
            try:
                mark("research", "running", f"PubMed done ({len(papers)}), searching Scholar")
                papers += await semanticscholar_search(f"{p.title} {p.problem}"[:200])
            except Exception as e:
                steps["research_error"] = (steps.get("research_error", "") + f" scholar: {e}").strip()
        except Exception as e:
            steps["research_error"] = str(e)
    kb = retrieve(db, brief, 4)
    mark("research", "running", f"synthesizing {len(papers)} papers")
    research_prompt = (f"Query: {brief[:500]}\nPapers: {str(papers)[:2500]}\nKnowledge: {kb[:1500]}\n"
                       "Summarize gaps, risks, 3 design implications with citations.")
    synthesis = await generate(research_prompt)
    steps["research"] = {"papers": papers, "paper_count": len(papers),
                         "synthesis": synthesis, "prompt": research_prompt}
    p.stage = "evidence"
    db.commit()
    log_run(db, p.id, "orchestrator", "full-run.research", brief[:200], f"{len(papers)} papers", status="ok")
    mark("research", "done", f"{len(papers)} papers synthesized")

    # 2. Spec
    mark("spec", "running", "drafting concepts + spec")
    spec_prompt = (f"PROJECT: {p.title}\nPROBLEM: {p.problem}\nUSERS: {p.users}\n"
                   f"CONSTRAINTS: {p.constraints}\nKNOWLEDGE:\n{kb[:2000]}\nEVIDENCE:\n{synthesis[:1500]}\n\n"
                   "Output: (1) 3 concepts scored on safety/printability/cost, "
                   "(2) chosen spec: dimensions, loads, materials, tolerances, cleaning, failure modes, "
                   "(3) open questions.")
    spec_text = await generate(spec_prompt)
    spec = {"concepts_text": spec_text,
            "dimensions_mm": {"max_envelope": [100, 100, 60]},
            "material_candidates": ["PLA", "PETG"], "min_wall_mm": 2.0,
            "status": "full-run draft — review before print"}
    p.spec_json = json.dumps(spec)
    p.stage = "design"
    db.commit()
    steps["spec"] = spec_text
    steps["spec_prompt"] = spec_prompt
    log_run(db, p.id, "orchestrator", "full-run.spec", p.title, spec_text[:500])
    mark("spec", "done", "spec drafted")

    # 3. Safety (report, don't block — user overrode gates)
    mark("safety", "running", "checking risk flags")
    text = f"{p.title} {p.problem} {spec_text[:1500]}"
    flags = sorted({w for w in HIGH_RISK if w in text.lower()})
    safety_prompt = (f"Design text: {text[:2000]}\nFlags: {flags}\n"
                     "Output: risk class, biocompat/cleaning concerns, pre-print verifications, one-line disclaimer.")
    review = await generate(safety_prompt)
    steps["safety"] = {"verdict": "BLOCKED — review required" if flags else "PASS with disclaimer",
                       "flags": flags, "review": review, "prompt": safety_prompt}
    log_run(db, p.id, "orchestrator", "full-run.safety", text[:200],
            steps["safety"]["verdict"], status="ok" if not flags else "flagged")
    mark("safety", "done", steps["safety"]["verdict"])

    # 4. Codegen loop
    attempts: list[dict] = []
    stl_file = None
    code = ""
    last_err = ""
    tries = max(1, min(body.max_codegen_tries, 5))
    for i in range(tries):
        mark("codegen", "running", f"code try {i + 1}/{tries}" + (f" — fixing: {last_err[:100]}" if last_err else " — generating"))
        prompt = (f"DESIGN BRIEF: {brief}\nSPEC:\n{spec_text[:1500]}\nKNOWLEDGE:\n{kb[:1200]}\n"
                  + (f"PREVIOUS CODE FAILED: {last_err}\n{code[:2000]}\nFix it. " if last_err
                     else "Generate the part. ") + "Reply with one ```python block only.")
        raw = await generate(prompt, system=CODEGEN_SYSTEM, max_tokens=2000)
        code = _extract_code(raw)
        blocked = [x for x in validate_code(code) if x.startswith("blocked")]
        if blocked:
            last_err = "; ".join(blocked)
            attempts.append({"try": i + 1, "ok": False, "error": last_err,
                             "code": code, "prompt": prompt, "raw": raw})
            continue
        stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        py_path = CAD_DIR / f"{p.id}_full_{stamp}_t{i}.py"
        py_path.write_text(code)
        out_path = CAD_DIR / f"{p.id}_full_{stamp}_t{i}.stl"
        mark("codegen", "running", f"try {i + 1}/{tries} — exporting STL")
        ok, note = try_build_stl(code, out_path)
        attempts.append({"try": i + 1, "ok": ok, "note": note,
                         "stl_file": str(out_path) if ok else None,
                         "code": code, "prompt": prompt, "raw": raw})
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
    mark("codegen", "done" if stl_file else "error", "STL built" if stl_file else f"failed: {last_err[:150]}")

    # 5. Validate + packet
    if stl_file:
        mark("print", "running", "validating mesh")
        try:
            import trimesh
            m = trimesh.load(stl_file)
            steps["validate"] = {"watertight": bool(m.is_watertight),
                                 "volume_mm3": float(m.volume) if m.is_volume else None,
                                 "faces": int(len(m.faces)),
                                 "bbox_mm": m.bounds.tolist()}
            mark("print", "running", f"watertight={m.is_watertight}, building packet")
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
        mark("print", "done", "packet ready")
    else:
        mark("print", "error", "no STL — nothing to validate")
    steps["stage"] = p.stage
    log_run(db, p.id, "orchestrator", "full-run.done", "", f"stage={p.stage} stl={stl_file}")
    return steps


@router.post("/full-run")
async def full_run(body: FullRun, db: Session = Depends(get_db)):
    """One click (blocking): research -> spec -> safety -> codegen -> validate -> packet."""
    return await _pipeline(db, body)


@router.post("/full-run-async")
async def full_run_async(body: FullRun):
    """Non-blocking: returns job_id immediately; poll GET /api/agent/jobs/{id}."""
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    jobs[job_id] = {"id": job_id, "project_id": body.project_id, "status": "queued",
                    "current": None, "steps": _fresh_steps(), "result": None, "error": None,
                    "created_at": datetime.datetime.utcnow().isoformat()}

    def report(step, status, detail=""):
        job = jobs.get(job_id)
        if not job:
            return
        job["steps"][step] = {"status": status, "detail": detail}
        job["current"] = step if status == "running" else job["current"]
        job["updated_at"] = datetime.datetime.utcnow().isoformat()

    async def _bg():
        db = SessionLocal()
        try:
            jobs[job_id]["status"] = "running"
            result = await _pipeline(db, body, report)
            jobs[job_id]["result"] = result
            jobs[job_id]["status"] = "done"
            jobs[job_id]["current"] = None
        except Exception as e:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = str(e)
        finally:
            db.close()

    asyncio.create_task(_bg())
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job
