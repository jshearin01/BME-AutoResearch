"""Knowledge base: ingest local notes/guidance, keyword retrieval for agents."""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.shared.db import get_db
from .models import KnowledgeChunk
from .store import chunk_text, score

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

SEED = [
    ("fda-class-i-basics",
     "FDA Class I devices are low-risk, often exempt from premarket notification (510k). "
     "Examples: bandages, examination gloves, manual surgical instruments. Even exempt devices "
     "must follow Quality System Regulation basics, labeling (21 CFR 801), and registration/listing. "
     "This harness builds research prototypes only — no FDA clearance implied."),
    ("fdm-design-rules",
     "FDM design rules for PLA/PETG: min wall 1.2mm (2mm for loaded parts), min hole dia 2mm, "
     "avoid overhangs >60deg without supports, orient flat side down, 3 walls + 20% gyroid infill "
     "for functional parts, brim for small footprints, dry PETG to reduce stringing."),
    ("biocompat-note",
     "PLA/PETG/TPU prints are NOT sterile or biocompatible by default. Layer lines harbor microbes. "
     "External, non-sterile prototypes only. No skin-breach, airway, implant, or dosing use without "
     "qualified review. Label every print NOT FOR CLINICAL USE with material lot + date."),
]


def ensure_seed(db: Session):
    if db.query(KnowledgeChunk).count() == 0:
        for src, text in SEED:
            for ch in chunk_text(text):
                db.add(KnowledgeChunk(source=src, text=ch))
        db.commit()


@router.get("/sources")
def sources(db: Session = Depends(get_db)):
    ensure_seed(db)
    rows = db.query(KnowledgeChunk.source).distinct().all()
    return {"sources": sorted(r[0] for r in rows),
            "count": db.query(KnowledgeChunk).count()}


@router.post("/ingest")
async def ingest(body: dict, db: Session = Depends(get_db)):
    ensure_seed(db)
    source = body.get("source", "note")[:120]
    text = body.get("text", "")
    chunks = chunk_text(text)
    for ch in chunks:
        db.add(KnowledgeChunk(source=source, text=ch))
    db.commit()
    return {"source": source, "chunks": len(chunks)}


@router.post("/upload")
async def upload(file: UploadFile = File(...), source: str = Form("upload"),
                 db: Session = Depends(get_db)):
    ensure_seed(db)
    raw = (await file.read()).decode("utf-8", errors="ignore")
    chunks = chunk_text(raw)
    for ch in chunks:
        db.add(KnowledgeChunk(source=source or file.filename, text=ch))
    db.commit()
    return {"file": file.filename, "chunks": len(chunks)}


@router.post("/query")
async def query(body: dict, db: Session = Depends(get_db)):
    ensure_seed(db)
    q = body.get("query", "")
    limit = min(int(body.get("limit", 5)), 20)
    rows = db.query(KnowledgeChunk).all()
    ranked = sorted(((score(q, r.text), r) for r in rows), key=lambda x: x[0], reverse=True)
    top = [{"source": r.source, "text": r.text, "score": round(s, 3)}
           for s, r in ranked[:limit] if s > 0]
    return {"query": q, "hits": top}


def retrieve(db: Session, query: str, limit: int = 4) -> str:
    """Sync helper for other agents — returns pasted context block."""
    ensure_seed(db)
    rows = db.query(KnowledgeChunk).all()
    ranked = sorted(((score(query, r.text), r) for r in rows), key=lambda x: x[0], reverse=True)
    top = [r for s, r in ranked[:limit] if s > 0]
    if not top:
        return ""
    return "\n".join(f"[{r.source}] {r.text}" for r in top)
