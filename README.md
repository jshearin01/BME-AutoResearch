# BiomedEng Agent Harness

Local LLM agent harness for biomedical engineering research: problem → evidence → solution → parametric CAD → validated STL → print.

FOSS defaults: FastAPI + React + CadQuery + Orca/PrusaSlicer + SQLite + ChromaDB (optional).

## Quickstart (no docker)

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env  # edit keys if you have them
uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open: frontend http://localhost:5173, API http://localhost:8000/docs

## Quickstart (docker)

```bash
docker-compose up --build
```

## Default test project

Seeded on first run: "One-handed pill bottle opener" — low risk, proves end-to-end loop.

## Human gates (mandatory)

1. Approve problem/need before design
2. Approve design spec before CAD
3. Approve STL before slice/print

> SAFETY: Research prototype only. Not a medical device. No implantable/invasive/sterile claims without qualified review. See `docs/safety/DISCLAIMER.md`.

## Layout

```
backend/app/modules/{projects,research,design,cad,safety,printing,runs}/
backend/app/shared/{config,db,llm,observability}/
backend/app/orchestrator.py
frontend/src/
cad-library/templates/ materials.yml printer-profiles/
docs/architecture/decisions/
```

## LLM providers

`LLM_PROVIDER=stub` (default, works with no keys) | `anthropic` | `openai` | `ollama`
Set keys in `.env`. Stub returns templated specs so UI works offline.
