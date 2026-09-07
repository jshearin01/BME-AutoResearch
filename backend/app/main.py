from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.shared.config import settings
from app.shared.db import init_db

from app.modules.projects.router import router as projects_router
from app.modules.research.router import router as research_router
from app.modules.design.router import router as design_router
from app.modules.cad.router import router as cad_router
from app.modules.safety.router import router as safety_router
from app.modules.printing.router import router as printing_router
from app.modules.runs.router import router as runs_router
from app.modules.knowledge.router import router as knowledge_router
from app.orchestrator import router as agent_router

app = FastAPI(title="BiomedEng Harness", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

for r in (projects_router, research_router, design_router, cad_router,
          safety_router, printing_router, runs_router, knowledge_router, agent_router):
    app.include_router(r)

init_db()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True, "provider": settings.LLM_PROVIDER,
            "note": "Research prototype only. Not a medical device."}
