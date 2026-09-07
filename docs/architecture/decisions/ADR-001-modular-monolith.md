# ADR-001: Modular monolith + FOSS CAD code-gen

Date: 2026-09-07
Status: accepted

Context: Solo dev, Mac, zero budget, need problem→print loop fast.
Decision:
- Modular monolith (FastAPI), SQLite, React+Vite, no microservices.
- CadQuery code-gen as primary CAD (parametric, versionable), OpenSCAD fallback.
- OrcaSlicer/PrusaSlicer CLI, generic FDM profiles.
- Stub LLM provider default; Anthropic/OpenAI/Ollama swappable.
- Human gates at problem/spec/STL.

Consequences: fast iteration, easy local run, extraction seams kept per-module.
Revisit when: multi-user, cloud slicing, or regulated path needed.
