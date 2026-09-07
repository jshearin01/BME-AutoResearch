"""Researcher: PubMed + Semantic Scholar (no key needed)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import httpx
from app.shared.db import get_db
from app.shared.observability import log_run
from app.shared.llm import generate

router = APIRouter(prefix="/api/research", tags=["research"])


async def pubmed_search(query: str, retmax: int = 5) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as c:
        s = await c.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                        params={"db": "pubmed", "term": query, "retmax": retmax, "retmode": "json"})
        s.raise_for_status()
        ids = s.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        e = await c.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                        params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
        e.raise_for_status()
        docs = e.json().get("result", {})
        out = []
        for i in ids:
            d = docs.get(i, {})
            out.append({"source": "pubmed", "id": i,
                        "title": d.get("title", ""),
                        "pubdate": d.get("pubdate", ""),
                        "authors": [a.get("name", "") for a in d.get("authors", [])][:4]})
        return out


async def semanticscholar_search(query: str, limit: int = 5) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get("https://api.semanticscholar.org/graph/v1/paper/search",
                        params={"query": query, "limit": limit,
                                "fields": "title,year,authors,citationCount,url,abstract"})
        r.raise_for_status()
        return [{"source": "semanticscholar", "title": p.get("title", ""),
                 "year": p.get("year"), "citations": p.get("citationCount"),
                 "url": p.get("url", ""), "abstract": (p.get("abstract") or "")[:500]}
                for p in r.json().get("data", [])]


@router.post("/search")
async def search(body: dict, db: Session = Depends(get_db)):
    query = body.get("query", "")
    project_id = body.get("project_id")
    papers: list[dict] = []
    errors: list[str] = []
    try:
        papers += await pubmed_search(query)
    except Exception as e:
        errors.append(f"pubmed: {e}")
    try:
        papers += await semanticscholar_search(query)
    except Exception as e:
        errors.append(f"semanticscholar: {e}")
    summary = await generate(
        f"Query: {query}\nPapers: {str(papers)[:3000]}\n"
        "Summarize: gaps, risks, 3 design implications. Cite sources by title."
    )
    log_run(db, project_id, "researcher", "research.search", query, f"{len(papers)} papers. {summary[:500]}")
    return {"query": query, "papers": papers, "synthesis": summary, "errors": errors}
