from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.shared.db import get_db
from app.shared.observability import log_run
from .models import Project, new_id
from .schemas import ProjectCreate, ProjectUpdate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])

SEED_ID = "proj_seed_opener"


def ensure_seed(db: Session):
    if not db.get(Project, SEED_ID):
        db.add(Project(
            id=SEED_ID,
            title="One-handed pill bottle opener",
            problem="Arthritis patients struggle with push-and-turn pill caps using one hand.",
            users="Older adults with limited grip strength",
            constraints="FDM printable, no sharp edges, easy-clean PLA/PETG, <100mm",
            stage="problem",
        ))
        db.commit()


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    ensure_seed(db)
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    ensure_seed(db)
    p = Project(id=new_id(), title=body.title, problem=body.problem,
                users=body.users, constraints=body.constraints)
    db.add(p)
    db.commit()
    db.refresh(p)
    log_run(db, p.id, "orchestrator", "project.create", body.title, p.id)
    return p


@router.get("/{pid}", response_model=ProjectOut)
def get_project(pid: str, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    return p


@router.patch("/{pid}", response_model=ProjectOut)
def update_project(pid: str, body: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    log_run(db, p.id, "orchestrator", "project.update", pid, f"stage={p.stage}")
    return p
