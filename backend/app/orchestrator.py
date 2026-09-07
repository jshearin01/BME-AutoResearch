"""Orchestrator: routes problem -> research -> design -> safety -> cad -> print.

Keeps handoffs small + validated. Human gates enforced in UI (stage field).
"""

from fastapi import APIRouter, Depends
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
