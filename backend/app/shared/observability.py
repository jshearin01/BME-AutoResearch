"""Trace every agent step to SQLite + stdout. Cheap observability before fancy tools."""

import datetime
from sqlalchemy.orm import Session
from app.modules.runs.models import RunLog


def log_run(db: Session, project_id: str | None, agent: str, action: str, input_summary: str = "", output_summary: str = "", status: str = "ok"):
    row = RunLog(
        project_id=project_id or "global",
        agent=agent,
        action=action,
        input_summary=input_summary[:8000],
        output_summary=output_summary[:16000],
        status=status,
        created_at=datetime.datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    print(f"[{row.created_at.isoformat()}] {agent}/{action} ({status}) :: {output_summary[:200]}")
    return row
