from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.shared.db import get_db
from .models import RunLog

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _row(r: RunLog) -> dict:
    return {"id": r.id, "project_id": r.project_id, "agent": r.agent, "action": r.action,
            "input_summary": r.input_summary, "output_summary": r.output_summary,
            "status": r.status, "created_at": r.created_at.isoformat() if r.created_at else None}


@router.get("")
def list_runs(project_id: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(RunLog).order_by(RunLog.id.desc())
    if project_id:
        q = q.filter(RunLog.project_id == project_id)
    rows = q.limit(min(limit, 500)).all()
    return [_row(r) for r in rows]


@router.get("/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    r = db.get(RunLog, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return _row(r)
